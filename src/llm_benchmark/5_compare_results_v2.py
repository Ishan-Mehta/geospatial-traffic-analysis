"""
Step 5 (v2) — Phase 4: compare LLM answers with Google's ground truth. Offline, NO API calls.

Inputs : gmaps/gmaps_queries.csv, gmaps/gmaps_routes.csv (final Google tags), llm/<model>_A.jsonl,
         llm/<model>_grounding_route_flags.csv, od_pairs.csv, candidate_pairs.csv, consistency_routes.csv,
         output/bangalore_drive.graphml (street-name list), output/flattened_traffic_data.csv +
         master_subroutes.csv (Stage-2 speeds for the naive baseline).
Outputs: results/comparison_<model>_<cond>.csv   one row per query × sample (git-ignored: contains Google/LLM data)
         results/route_metrics_<model>_<cond>.csv per-route aggregates (git-ignored)
         results/road_name_matches_<model>.csv    each distinct LLM road name → best OSM name (git-ignored)
         results/summary_*.csv                    aggregate tables (committed)
         figures/phase4/r01…r11 plots             (committed)
Metric definitions: docs/benchmark_v2/METHODOLOGY.md §7. Usage: python 5_compare_results_v2.py [--model KEY] [--condition A]
"""

import argparse
import json
import re
import time

import numpy as np
import pandas as pd

import config as C
from v2_common import edge_names, haversine_m, read_jsonl, token_set_ratio

RNG_SEED = 20261001
N_BOOT = 2000
LABEL_NUM = {"none": 0, "light": 1, "moderate": 2, "heavy": 3}
SLOTS = [s["id"] for s in C.TIME_SLOTS]
PEAKS = ("AM_PEAK", "PM_PEAK")
MATCH_MIN = 85                                    # fuzzy score for "same road"


# =====================================================================
#  Road-name normalisation and matching (METHODOLOGY §7.5)
# =====================================================================
GENERIC = {"road", "main", "cross", "street", "lane", "avenue", "highway", "service", "the", "of", "and",
           "junction", "circle", "flyover", "underpass", "bridge", "nagar", "layout", "stage", "block",
           "phase", "sector", "extension", "new", "old", "outer", "inner", "ring", "national", "state"}
NON_ROADS = {"service road", "unnamed road", "road", ""}
_ABBR = [(r"\brd\b", "road"), (r"\bmn\b", "main"), (r"\bext\b", "extension"), (r"\bblvd\b", "boulevard"),
         (r"\borr\b", "outer ring road"), (r"\birr\b", "inner ring road"), (r"\bjn\b", "junction"),
         (r"\bnh\s*(\d+)", r"national highway \1"), (r"\bsh\s*(\d+)", r"state highway \1"),
         (r"\bst\b\s*$", "street")]                # trailing "St" = street; leading "St" (Saint) kept


ALIASES = {"mg road": "mahatma gandhi road", "m g road": "mahatma gandhi road", "cmh road": "chinmaya mission hospital road",
           "otc road": "old taluk cutchery road", "kg road": "kempegowda road", "k g road": "kempegowda road",
           "sjp road": "sri jayachamarajendra road", "jc road": "jc road", "kr road": "krishnarajendra road",
           "hal airport road": "hal old airport road", "old airport road": "hal old airport road",
           "airport road": "hal old airport road", "mehkri circle": "mekhri circle", "nh 44": "national highway 44"}


def norm_road(s: str) -> str:
    s = str(s).lower().replace("&", " and ").replace("'", "").replace("\u2019", "")
    s = re.sub(r"\(.*?\)", " ", s)
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    for a, b in _ABBR:
        s = re.sub(a, b, s)
    s = re.sub(r"\s+", " ", s).strip()
    return ALIASES.get(s, s)


def compact(s: str) -> str:
    return s.replace(" ", "")


def road_score(a: str, b: str) -> float:
    """Fuzzy similarity of two normalised names: token-set ratio, or character ratio ignoring spaces
    (catches 'vani vilas' vs 'vanivilas', 'nrupathunga' vs 'nrupatunga')."""
    import difflib
    return max(token_set_ratio(a, b), 100 * difflib.SequenceMatcher(None, compact(a), compact(b)).ratio())


def distinctive(n: str) -> set:
    return {t for t in n.split() if t not in GENERIC and not re.fullmatch(r"\d+(st|nd|rd|th)?", t)}


class RoadMatcher:
    """Fuzzy match free-text road names to the OSM street-name list of Bangalore (cached per name)."""

    def __init__(self, osm_names: set):
        self.names = osm_names
        self.index = {}
        for n in osm_names:
            keys = set(distinctive(n) or set(n.split()))
            d = "".join(sorted(distinctive(n), key=n.split().index)) if distinctive(n) else ""
            if len(d) >= 5:
                keys.add("~" + d[:5])                      # prefix of the joined distinctive words
            keys |= {"~" + t[:5] for t in distinctive(n) if len(t) >= 5}
            for k in keys:
                self.index.setdefault(k, set()).add(n)
        self.cache = {}

    def best(self, raw: str):
        n = norm_road(raw)
        if n in self.cache:
            return self.cache[n]
        if n in NON_ROADS:
            res = (n, None, 0.0, "generic")
        elif n in self.names:
            res = (n, n, 100.0, "exact")
        else:
            toks = distinctive(n)
            if not toks:                           # e.g. "12th Main Road": only an exact match counts
                res = (n, None, 0.0, "generic")
            else:
                joined = "".join(t for t in n.split() if t in toks)
                keys = toks | {"~" + t[:5] for t in toks if len(t) >= 5} | ({"~" + joined[:5]} if len(joined) >= 5 else set())
                cand = set().union(*[self.index.get(k, set()) for k in keys])
                if not cand:
                    res = (n, None, 0.0, "no_candidate")
                else:
                    b = max(cand, key=lambda c: (road_score(n, c), -abs(len(c) - len(n))))
                    sc = road_score(n, b)
                    res = (n, b if sc >= MATCH_MIN else None, round(sc, 1), "fuzzy")
        self.cache[n] = res
        return res


def set_overlap(llm: list, google: list):
    """Greedy fuzzy matching between two road-name sets (normalised). Returns jaccard, precision, recall."""
    L = [x for x in dict.fromkeys(llm) if x and x not in NON_ROADS]
    G = [x for x in dict.fromkeys(google) if x and x not in NON_ROADS]
    if not L or not G:
        return np.nan, np.nan, np.nan, 0
    used, hits = set(), 0
    for a in L:
        best, bs = None, 0
        for b in G:
            if b in used:
                continue
            s = 100.0 if a == b else road_score(a, b) if (distinctive(a) & distinctive(b) or
                                                           compact(a)[:5] == compact(b)[:5]) else 0.0
            if s > bs:
                best, bs = b, s
        if best is not None and bs >= MATCH_MIN:
            used.add(best)
            hits += 1
    union = len(L) + len(G) - hits
    return hits / union, hits / len(L), hits / len(G), hits


# =====================================================================
#  Statistics helpers (route-level cluster bootstrap)
# =====================================================================
def boot_median_ci(values_by_route: pd.Series, rng) -> tuple:
    """95 % CI of the median of per-route values, resampling routes."""
    v = values_by_route.dropna().values
    if len(v) < 3:
        return (np.nan, np.nan)
    meds = np.median(rng.choice(v, size=(N_BOOT, len(v)), replace=True), axis=1)
    return tuple(np.percentile(meds, [2.5, 97.5]).round(4))


def perm_test_median(a: np.ndarray, b: np.ndarray, rng, n=5000) -> float:
    """Two-sided permutation p-value for the difference in medians (route-level values)."""
    a, b = a[~np.isnan(a)], b[~np.isnan(b)]
    if len(a) < 3 or len(b) < 3:
        return np.nan
    obs = abs(np.median(a) - np.median(b))
    pool = np.concatenate([a, b])
    cnt = 0
    for _ in range(n):
        rng.shuffle(pool)
        if abs(np.median(pool[:len(a)]) - np.median(pool[len(a):])) >= obs:
            cnt += 1
    return (cnt + 1) / (n + 1)


def spearman(x, y) -> float:
    s = pd.DataFrame({"x": x, "y": y}).dropna()
    return float(s.x.rank().corr(s.y.rank())) if len(s) > 2 else np.nan


# =====================================================================
#  Naive baseline (METHODOLOGY §7.8): straight line × detour, at a typical Stage-2 speed per slot
# =====================================================================
def stage2_speeds() -> dict:
    """Median speed (km/h) per (slot, weekday/weekend) from the April Stage-2 scrape (different routes, different
    week — independent of the benchmark), using plausible legs ≥ 1 km, snapshots within ±90 min of the slot time."""
    flat = pd.read_csv(C.FLATTENED_TRAFFIC_CSV)
    master = pd.read_csv(C.MASTER_SUBROUTES_CSV)
    master["straight"] = haversine_m(master.start_lat, master.start_lng, master.end_lat, master.end_lng)
    lat0, lat1, lng0, lng1 = C.V2_LEG_BBOX
    ok = (master.distance_meters >= 1000) & (master.distance_meters <= master.straight * C.V2_LEG_MAX_DETOUR) & \
         master.start_lat.between(lat0, lat1) & master.end_lat.between(lat0, lat1) & \
         master.start_lng.between(lng0, lng1) & master.end_lng.between(lng0, lng1)
    f = flat.merge(master[ok][["sub_route_id", "distance_meters"]], on="sub_route_id")
    f = f[f.live_duration_s > 0]
    ts = pd.to_datetime(f.timestamp, utc=True).dt.tz_convert("Asia/Kolkata")
    f["mins"] = ts.dt.hour * 60 + ts.dt.minute
    f["weekend"] = ts.dt.dayofweek >= 5
    f["kmh"] = f.distance_meters / f.live_duration_s * 3.6
    out = {}
    for s in C.TIME_SLOTS:
        h, m = map(int, s["time"].split(":"))
        t = h * 60 + m
        near = ((f.mins - t) % 1440).where(((f.mins - t) % 1440) <= 720, 1440 - ((f.mins - t) % 1440)) <= 90
        for wk in (False, True):
            sub = f[near & (f.weekend == wk)]
            out[(s["id"], wk)] = (float(sub.kmh.median()), int(len(sub)))
    return out


# =====================================================================
def load(model: str, cond: str):
    d = C.V2_DIR
    gq = pd.read_csv(d / "gmaps" / C.V2_GMAPS_QUERIES_CSV)
    gr = pd.read_csv(d / "gmaps" / C.V2_GMAPS_ROUTES_CSV)
    od = pd.read_csv(C.V2_OD_PAIRS_CSV)
    recs = [r for r in read_jsonl(C.V2_LLM_DIR / f"{model}_{cond}.jsonl") if r.get("status") == "ok"]
    llm = pd.DataFrame([{
        "route_id": r["route_id"], "day": r["day"], "slot_id": r["slot_id"], "sample_idx": r["sample_idx"],
        "llm_km": r["parsed_response"]["estimated_distance_km"], "llm_min": r["parsed_response"]["estimated_time_minutes"],
        "llm_label": r["parsed_response"]["traffic_awareness"], "llm_roads": r["parsed_response"]["suggested_route"],
        "valid_numbers": r.get("valid_numbers", True), "thought_tokens": r.get("thought_tokens"),
        "model_version": r.get("model_version")} for r in recs])
    llm = llm.drop_duplicates(["route_id", "day", "slot_id", "sample_idx"], keep="last")
    flags_path = C.V2_LLM_DIR / f"{model}_grounding_route_flags.csv"
    flags = pd.read_csv(flags_path)[["route_id", "grounding_flag"]] if flags_path.exists() else None
    return gq, gr, od, llm, flags


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", default=C.V2_ACTIVE_LLM)
    ap.add_argument("--condition", default="A", choices=["A", "B"])
    args = ap.parse_args()
    t0 = time.time()
    rng = np.random.default_rng(RNG_SEED)
    res_dir = C.V2_DIR / "results"
    fig_dir = C.V2_FIGURES_DIR / "phase4"
    res_dir.mkdir(parents=True, exist_ok=True)
    tag = f"{args.model}_{args.condition}"

    gq, gr, od, llm, flags = load(args.model, args.condition)
    print(f"Loaded: {len(gq)} Google queries, {len(llm)} LLM answers ({llm.sample_idx.value_counts().to_dict()})", flush=True)

    # ---------------- join ----------------
    tags = gr[["route_id", "band_google", "road_type_google", "hotspot_exposure_google", "arterial_share_google",
               "hotspot_share_google", "google_distance_m", "n_distinct_paths"]]
    df = llm.merge(gq[["route_id", "day", "slot_id", "is_weekend", "calendar_note", "distance_m", "duration_s",
                       "static_duration_s", "traffic_index", "osm_road_seq", "google_step_roads", "endpoints_ok"]],
                   on=["route_id", "day", "slot_id"], how="inner")
    df = df.merge(tags, on="route_id").merge(od[["route_id", "origin_name", "dest_name", "straight_m"]], on="route_id")
    if flags is not None:
        df = df.merge(flags, on="route_id", how="left")
    df["calendar_note"] = df.calendar_note.fillna("")
    df["g_km"], df["g_min"], df["g_static_min"] = df.distance_m / 1000, df.duration_s / 60, df.static_duration_s / 60
    df["llm_label_num"] = df.llm_label.map(LABEL_NUM)
    df["lr_dist"] = np.log(df.llm_km / df.g_km)
    df["lr_time"] = np.log(df.llm_min / df.g_min)
    df["lr_time_static"] = np.log(df.llm_min / df.g_static_min)
    df["abs_err_km"] = (df.llm_km - df.g_km).abs()
    df["abs_err_min"] = (df.llm_min - df.g_min).abs()
    df["ape_dist"] = df.abs_err_km / df.g_km
    df["ape_time"] = df.abs_err_min / df.g_min
    df["over_dist"], df["over_time"] = df.llm_km > df.g_km, df.llm_min > df.g_min
    df["day_type"] = np.where(df.is_weekend, "weekend", "weekday")
    print(f"Joined rows: {len(df)} (all endpoints OK: {bool(df.endpoints_ok.all())})", flush=True)

    # ---------------- naive baseline ----------------
    speeds = stage2_speeds()
    detour = float((lambda c: np.median(c.osm_m / c.straight_m))(
        pd.read_csv(C.V2_CANDIDATE_PAIRS_CSV).query("eligible")))
    df["base_km"] = df.straight_m / 1000 * detour
    df["base_kmh"] = [speeds[(s, w)][0] for s, w in zip(df.slot_id, df.is_weekend)]
    df["base_min"] = df.base_km / df.base_kmh * 60
    df["lr_dist_base"] = np.log(df.base_km / df.g_km)
    df["lr_time_base"] = np.log(df.base_min / df.g_min)
    df["llm_beats_base_time"] = df.lr_time.abs() < df.lr_time_base.abs()
    df["llm_beats_base_dist"] = df.lr_dist.abs() < df.lr_dist_base.abs()
    print(f"Baseline: detour {detour:.3f}; Stage-2 speeds km/h " +
          ", ".join(f"{k[0]}{'-we' if k[1] else ''} {v[0]:.1f}" for k, v in speeds.items()), flush=True)

    # ---------------- road names ----------------
    import osmnx as ox
    G = ox.load_graphml(C.OSM_GRAPH_PATH)
    osm_names = {norm_road(n) for _, _, d in G.edges(data=True) for n in edge_names(d)} - NON_ROADS
    # Reference list of real road names (D-55): OSM drive-graph names are incomplete (~3,100), so add every road
    # name Google used in its 2,016 step instructions and the BBMP arterial/sub-arterial road list.
    google_names = {norm_road(x) for v in gq.google_step_roads.dropna() for x in str(v).split(" | ")} - NON_ROADS
    bbmp = pd.read_csv(C._PROJECT_ROOT / "data" / "raw" / "data_blr_roads_total.csv")["Name of the Road"].dropna()
    bbmp_names = {norm_road(p) for v in bbmp for p in re.split(r"\s+-\s+|/|,", str(v)) if len(p.strip()) > 3} - NON_ROADS
    ref_names = osm_names | google_names | bbmp_names
    matcher = RoadMatcher(ref_names)
    print(f"Reference road names: OSM {len(osm_names):,} + Google steps {len(google_names):,} + BBMP {len(bbmp_names):,} "
          f"= {len(ref_names):,} distinct (graph loaded {time.time() - t0:.0f}s)", flush=True)

    val_rows, jac, prec, rec, n_l, n_valid = [], [], [], [], [], []
    for roads, oseq, steps in zip(df.llm_roads, df.osm_road_seq, df.google_step_roads):
        matched = [matcher.best(x) for x in roads]
        canon = [m[1] or m[0] for m in matched]
        g_names = [norm_road(x) for x in str(oseq).split(" | ") + str(steps).split(" | ") if x and x != "nan"]
        g_canon = [(matcher.best(x)[1] or matcher.best(x)[0]) for x in g_names]
        j, p, r_, _ = set_overlap(canon, g_canon)
        jac.append(j), prec.append(p), rec.append(r_)
        named = [m for m in matched if m[3] != "generic" or m[1]]
        n_l.append(len(named))
        n_valid.append(sum(1 for m in named if m[1]))
    df["jaccard_roads"], df["precision_roads"], df["recall_roads"] = jac, prec, rec
    df["n_llm_roads_named"], df["n_llm_roads_valid"] = n_l, n_valid
    df["validity_share"] = np.where(df.n_llm_roads_named > 0, df.n_llm_roads_valid / df.n_llm_roads_named, np.nan)
    names_tbl = pd.DataFrame([{"normalised": k, "best_osm": v[1], "score": v[2], "kind": v[3]}
                              for k, v in matcher.cache.items()])
    names_tbl.to_csv(res_dir / f"road_name_matches_{args.model}.csv", index=False)
    print(f"Road names: {len(names_tbl)} distinct normalised names; matched {names_tbl.best_osm.notna().mean():.0%}", flush=True)

    df.drop(columns=["llm_roads"]).assign(llm_roads=[" | ".join(x) for x in df.llm_roads]).to_csv(
        res_dir / f"comparison_{tag}.csv", index=False)

    # ---------------- main sample (sample 0) ----------------
    m0 = df[df.sample_idx == 0].copy()
    route = m0.groupby("route_id").agg(
        band=("band_google", "first"), road_type=("road_type_google", "first"),
        exposure=("hotspot_exposure_google", "first"), arterial_share=("arterial_share_google", "first"),
        hotspot_share=("hotspot_share_google", "first"), g_km=("g_km", "median"),
        med_lr_dist=("lr_dist", "median"), med_lr_time=("lr_time", "median"),
        med_abs_lr_dist=("lr_dist", lambda x: x.abs().median()), med_abs_lr_time=("lr_time", lambda x: x.abs().median()),
        med_ape_dist=("ape_dist", "median"), med_ape_time=("ape_time", "median"),
        validity=("validity_share", "mean"), jaccard=("jaccard_roads", "mean"), recall=("recall_roads", "mean"),
        precision=("precision_roads", "mean"), n_paths=("n_distinct_paths", "first"))
    # time-of-day sensitivity per route
    def pn(df_, col):
        wk = df_[df_.day_type == "weekday"]
        return wk[wk.slot_id.isin(PEAKS)][col].mean() / wk[wk.slot_id == "NIGHT"][col].mean()
    route["pn_llm"] = m0.groupby("route_id").apply(lambda x: pn(x, "llm_min"), include_groups=False)
    route["pn_google"] = m0.groupby("route_id").apply(lambda x: pn(x, "g_min"), include_groups=False)
    route["pn_log_diff"] = np.log(route.pn_llm / route.pn_google)
    route["within_route_rho_time"] = m0.groupby("route_id").apply(lambda x: spearman(x.llm_min, x.g_min),
                                                                  include_groups=False)
    route["label_rho"] = m0.groupby("route_id").apply(lambda x: spearman(x.llm_label_num, x.traffic_index),
                                                      include_groups=False)
    route.to_csv(res_dir / f"route_metrics_{tag}.csv")

    def summarise(rows: pd.DataFrame, routes: pd.DataFrame, label: str) -> dict:
        # route-level medians computed from THIS subset's rows (bug fix R-40: CIs used all rows for slot/day groups)
        rr = rows.groupby("route_id").agg(med_lr_dist=("lr_dist", "median"), med_lr_time=("lr_time", "median"))
        ci = lambda col: tuple(float(x) for x in np.exp(boot_median_ci(rr[col], rng)).round(3))
        return {
            "group": label, "n_routes": rows.route_id.nunique(), "n_queries": len(rows),
            "dist_ratio_median": round(float(np.exp(rows.lr_dist.median())), 3),
            "dist_ratio_ci95": ci("med_lr_dist"),
            "dist_ape_median": round(float(rows.ape_dist.median()), 3),
            "dist_over_share": round(float(rows.over_dist.mean()), 3),
            "time_ratio_median": round(float(np.exp(rows.lr_time.median())), 3),
            "time_ratio_ci95": ci("med_lr_time"),
            "time_ape_median": round(float(rows.ape_time.median()), 3),
            "time_abs_err_min_median": round(float(rows.abs_err_min.median()), 2),
            "time_over_share": round(float(rows.over_time.mean()), 3),
            "label_spearman": round(spearman(rows.llm_label_num, rows.traffic_index), 3),
            "road_validity_mean": round(float(rows.validity_share.mean()), 3),
            "road_jaccard_mean": round(float(rows.jaccard_roads.mean()), 3),
            "road_recall_mean": round(float(rows.recall_roads.mean()), 3),
            "road_precision_mean": round(float(rows.precision_roads.mean()), 3),
            "llm_beats_baseline_time": round(float(rows.llm_beats_base_time.mean()), 3),
            "llm_beats_baseline_dist": round(float(rows.llm_beats_base_dist.mean()), 3),
        }

    rows = [summarise(m0, route, "ALL")]
    for col, rcol in (("band_google", "band"), ("road_type_google", "road_type"), ("hotspot_exposure_google", "exposure")):
        for val, sub in m0.groupby(col):
            rows.append(summarise(sub, route[route[rcol] == val], f"{col}={val}"))
    for val, sub in m0.groupby("slot_id"):
        rows.append(summarise(sub, route, f"slot={val}"))
    for val, sub in m0.groupby("day_type"):
        rows.append(summarise(sub, route, f"day_type={val}"))
    sat = m0[m0.day == "Saturday"]
    rows.append(summarise(sat, route, "Saturday (holiday 10 Oct)"))
    rows.append(summarise(m0[m0.day == "Sunday"], route, "Sunday"))
    summary = pd.DataFrame(rows)
    summary.to_csv(res_dir / "summary_by_group.csv", index=False)

    # group differences (route level, permutation tests)
    tests = []
    for rcol, a, b in (("road_type", "arterial", "sub_arterial"), ("road_type", "arterial", "mixed"),
                       ("exposure", "high", "low"), ("band", "B1_1-5km", "B3_12-25km")):
        for metric in ("med_abs_lr_dist", "med_abs_lr_time", "med_lr_time", "validity", "jaccard"):
            A_, B_ = route[route[rcol] == a][metric].values, route[route[rcol] == b][metric].values
            tests.append({"factor": rcol, "a": a, "b": b, "metric": metric, "median_a": round(float(np.nanmedian(A_)), 4),
                          "median_b": round(float(np.nanmedian(B_)), 4), "n_a": len(A_), "n_b": len(B_),
                          "perm_p": round(perm_test_median(A_.astype(float), B_.astype(float), rng), 4)})
    pd.DataFrame(tests).to_csv(res_dir / "summary_group_tests.csv", index=False)

    # length-controlled checks (R-41): short routes have larger errors and hold half the sub-arterial routes,
    # so repeat the road-type comparison on routes >= 5 km, and correlate with arterial share within each band
    strat = []
    big = route[route.band != C.V2_BANDS[0][0]]
    for metric in ("med_abs_lr_dist", "med_abs_lr_time", "jaccard", "recall", "validity"):
        A_, B_ = big[big.road_type == "arterial"][metric].values, big[big.road_type == "sub_arterial"][metric].values
        strat.append({"check": "arterial vs sub-arterial, routes >= 5 km", "metric": metric,
                      "value_a": round(float(np.nanmedian(A_)), 4), "value_b": round(float(np.nanmedian(B_)), 4),
                      "n_a": len(A_), "n_b": len(B_), "perm_p": round(perm_test_median(A_.astype(float), B_.astype(float), rng), 4)})
    for band, g in route.groupby("band"):
        for metric in ("med_abs_lr_dist", "med_abs_lr_time", "jaccard"):
            strat.append({"check": f"spearman(arterial_share, metric) within {band}", "metric": metric,
                          "value_a": round(spearman(g.arterial_share, g[metric]), 3), "value_b": np.nan,
                          "n_a": len(g), "n_b": np.nan, "perm_p": np.nan})
    pd.DataFrame(strat).to_csv(res_dir / "summary_length_controlled.csv", index=False)

    # continuous relations (route level)
    cont = []
    for x in ("arterial_share", "hotspot_share", "g_km"):
        for y in ("med_abs_lr_dist", "med_abs_lr_time", "med_lr_time", "validity", "jaccard", "recall"):
            cont.append({"x": x, "y": y, "spearman": round(spearman(route[x], route[y]), 3), "n_routes": len(route)})
    pd.DataFrame(cont).to_csv(res_dir / "summary_continuous.csv", index=False)

    # time-of-day profile: median of time / route's weekday-night time
    for src, col in (("llm", "llm_min"), ("google", "g_min")):
        ref = m0[(m0.day_type == "weekday") & (m0.slot_id == "NIGHT")].groupby("route_id")[col].mean()
        m0[f"{src}_rel_night"] = m0[col] / m0.route_id.map(ref)
    tod = m0.groupby(["day_type", "slot_id"]).agg(
        llm_rel_night=("llm_rel_night", "median"), google_rel_night=("google_rel_night", "median"),
        time_ratio=("lr_time", lambda x: float(np.exp(x.median()))),
        llm_heavy_share=("llm_label", lambda x: (x == "heavy").mean()),
        google_traffic_index=("traffic_index", "median")).round(3).reindex(SLOTS, level=1)
    tod.to_csv(res_dir / "summary_time_of_day.csv")

    lab = m0.groupby("llm_label").agg(n=("traffic_index", "size"), traffic_index_median=("traffic_index", "median"),
                                      traffic_index_q25=("traffic_index", lambda x: x.quantile(.25)),
                                      traffic_index_q75=("traffic_index", lambda x: x.quantile(.75))).round(3)
    lab = lab.reindex([k for k in LABEL_NUM if k in lab.index])
    lab.to_csv(res_dir / "summary_traffic_labels.csv")

    overall = {
        "model": args.model, "condition": args.condition, "n_queries": len(m0), "n_routes": m0.route_id.nunique(),
        "time_of_day_pn_llm_median": round(float(route.pn_llm.median()), 3),
        "time_of_day_pn_google_median": round(float(route.pn_google.median()), 3),
        "time_of_day_pn_log_diff_median": round(float(route.pn_log_diff.median()), 3),
        "time_of_day_pn_rho_across_routes": round(spearman(route.pn_llm, route.pn_google), 3),
        "within_route_time_rho_median": round(float(route.within_route_rho_time.median()), 3),
        "within_route_label_rho_median": round(float(route.label_rho.median()), 3),
        "label_spearman_all": round(spearman(m0.llm_label_num, m0.traffic_index), 3),
        "llm_vs_google_static_time_ratio_median": round(float(np.exp(m0.lr_time_static.median())), 3),
        "baseline_detour": round(detour, 3),
        "baseline_time_ratio_median": round(float(np.exp(m0.lr_time_base.median())), 3),
        "baseline_dist_ratio_median": round(float(np.exp(m0.lr_dist_base.median())), 3),
        "baseline_abs_lr_time_median": round(float(m0.lr_time_base.abs().median()), 3),
        "llm_abs_lr_time_median": round(float(m0.lr_time.abs().median()), 3),
        "baseline_abs_lr_dist_median": round(float(m0.lr_dist_base.abs().median()), 3),
        "llm_abs_lr_dist_median": round(float(m0.lr_dist.abs().median()), 3),
        "road_names_distinct": len(names_tbl), "road_names_matched_share": round(float(names_tbl.best_osm.notna().mean()), 3),
        "grounding_flagged_routes": int(df.get("grounding_flag", pd.Series(dtype=bool)).fillna(False).astype(bool)
                                        .groupby(df.route_id).first().sum()) if "grounding_flag" in df else None,
        "thought_tokens_reported": int(m0.thought_tokens.notna().sum()),
    }
    pd.Series(overall).to_csv(res_dir / "summary_overall.csv", header=["value"])

    # consistency (samples 0-2)
    cons = df[df.groupby(["route_id", "day", "slot_id"]).sample_idx.transform("nunique") == 3]
    crows = []
    for k, g in cons.groupby(["route_id", "day", "slot_id"]):
        sets = [set(norm_road(x) for x in r) for r in g.llm_roads]
        jp = [len(a & b) / len(a | b) if (a | b) else np.nan for i, a in enumerate(sets) for b in sets[i + 1:]]
        crows.append({"cv_km": g.llm_km.std(ddof=0) / g.llm_km.mean(), "cv_min": g.llm_min.std(ddof=0) / g.llm_min.mean(),
                      "label_same": g.llm_label.nunique() == 1, "roads_jaccard_between_samples": np.nanmean(jp),
                      "range_lr_time": np.log(g.llm_min.max() / g.llm_min.min())})
    cdf = pd.DataFrame(crows)
    consistency = pd.Series({
        "n_queries_with_3_samples": len(cdf), "cv_distance_median": round(float(cdf.cv_km.median()), 4),
        "cv_time_median": round(float(cdf.cv_min.median()), 4), "label_identical_share": round(float(cdf.label_same.mean()), 3),
        "roads_jaccard_between_samples_mean": round(float(cdf.roads_jaccard_between_samples.mean()), 3),
        "time_max_over_min_median": round(float(np.exp(cdf.range_lr_time.median())), 3),
        "error_time_abs_lr_median_main": round(float(m0.lr_time.abs().median()), 3)})
    consistency.to_csv(res_dir / "summary_consistency.csv", header=["value"])

    base = pd.DataFrame([{"slot": k[0], "weekend": k[1], "stage2_median_kmh": round(v[0], 2), "n_snapshots": v[1]}
                         for k, v in speeds.items()])
    base.to_csv(res_dir / "summary_baseline_speeds.csv", index=False)

    print("\n=== OVERALL ===")
    print(pd.Series(overall).to_string())
    print("\n=== BY GROUP (sample 0) ===")
    print(summary[["group", "n_routes", "dist_ratio_median", "time_ratio_median", "time_ape_median", "label_spearman",
                   "road_validity_mean", "road_jaccard_mean", "llm_beats_baseline_time"]].to_string(index=False))
    print("\n=== CONSISTENCY ===")
    print(consistency.to_string())

    make_plots(df, m0, route, tod, lab, cdf, fig_dir)
    print(f"\nDone in {time.time() - t0:.0f}s -> {res_dir} and {fig_dir}", flush=True)


# =====================================================================
#  Plots
# =====================================================================
def make_plots(df, m0, route, tod, lab, cdf, fig_dir):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import seaborn as sns
    fig_dir.mkdir(parents=True, exist_ok=True)
    band_order = [b[0] for b in C.V2_BANDS]
    rt_order = ["arterial", "mixed", "sub_arterial"]

    def save(fig, name):
        fig.savefig(fig_dir / name, dpi=150, bbox_inches="tight")
        plt.close(fig)

    def guarded(fn):
        try:
            fn()
        except Exception as e:                        # one failing plot must not stop the others
            print(f"  plot skipped ({fn.__name__}): {e}")

    def r01():
        fig, ax = plt.subplots(figsize=(7, 6.5))
        sns.scatterplot(data=m0, x="g_km", y="llm_km", hue="band_google", hue_order=band_order, s=12, alpha=.5, ax=ax)
        lim = [1, 40]
        ax.plot(lim, lim, "k:", label="LLM = Google")
        ax.set(xscale="log", yscale="log", xlim=lim, ylim=lim, xlabel="Google distance (km)", ylabel="LLM distance (km)",
               title=f"r01 — Distance: LLM vs Google (median ratio {np.exp(m0.lr_dist.median()):.2f})")
        ax.legend(fontsize=8)
        save(fig, "r01_distance_scatter.png")

    def r02():
        fig, ax = plt.subplots(figsize=(7, 6.5))
        sns.scatterplot(data=m0, x="g_min", y="llm_min", hue="slot_id", hue_order=SLOTS, s=12, alpha=.5, ax=ax)
        lim = [4, 200]
        ax.plot(lim, lim, "k:", label="LLM = Google")
        ax.set(xscale="log", yscale="log", xlim=lim, ylim=lim, xlabel="Google predicted time (min)",
               ylabel="LLM time (min)", title=f"r02 — Time: LLM vs Google (median ratio {np.exp(m0.lr_time.median()):.2f})")
        ax.legend(fontsize=8)
        save(fig, "r02_time_scatter.png")

    def r03():
        d = m0.assign(llm=np.exp(m0.lr_time), baseline=np.exp(m0.lr_time_base)).melt(
            id_vars=["slot_id", "day_type"], value_vars=["llm", "baseline"], var_name="estimator", value_name="ratio")
        fig, ax = plt.subplots(figsize=(10, 5))
        sns.boxplot(data=d, x="slot_id", y="ratio", hue="estimator", order=SLOTS, showfliers=False, ax=ax)
        ax.axhline(1, color="k", ls=":")
        ax.set(yscale="log", ylabel="estimated ÷ Google time (log scale)",
               title="r03 — Time ratio by slot: LLM vs naive baseline (1 = matches Google)")
        save(fig, "r03_time_ratio_by_slot.png")

    def r04():
        fig, axes = plt.subplots(1, 2, figsize=(13, 4.5), sharey=True)
        for ax, dt in zip(axes, ("weekday", "weekend")):
            t = tod.loc[dt]
            ax.plot(SLOTS, t.google_rel_night.values, "o-", label="Google", lw=2)
            ax.plot(SLOTS, t.llm_rel_night.values, "s--", label="LLM", lw=2)
            ax.axhline(1, color="k", ls=":")
            ax.set(title=f"r04 — {dt}: time relative to the route's weekday-night time", ylabel="median ratio")
            ax.legend()
        save(fig, "r04_time_of_day_profile.png")

    def r05():
        fig, ax = plt.subplots(figsize=(6.5, 6))
        sns.scatterplot(data=route, x="pn_google", y="pn_llm", hue="band", hue_order=band_order, ax=ax)
        mx = max(route.pn_google.max(), route.pn_llm.max()) * 1.05
        ax.plot([0.8, mx], [0.8, mx], "k:", label="LLM = Google")
        ax.set(xlabel="Google peak ÷ night (weekday)", ylabel="LLM peak ÷ night (weekday)",
               title=f"r05 — Time-of-day sensitivity per route (ρ = {spearman(route.pn_llm, route.pn_google):.2f})")
        ax.legend(fontsize=8)
        save(fig, "r05_peak_night_ratio.png")

    def r06():
        order = [k for k in LABEL_NUM if k in set(m0.llm_label)]
        fig, ax = plt.subplots(figsize=(8, 5))
        sns.boxplot(data=m0, x="llm_label", y="traffic_index", order=order, showfliers=False, ax=ax)
        ax.set(xlabel="LLM traffic label", ylabel="Google traffic index (time ÷ route's fastest)",
               title=f"r06 — Traffic awareness (Spearman ρ = {spearman(m0.llm_label_num, m0.traffic_index):.2f})")
        for i, k in enumerate(order):
            ax.text(i, ax.get_ylim()[1] * 0.98, f"n={int((m0.llm_label == k).sum())}", ha="center", va="top", fontsize=8)
        save(fig, "r06_traffic_label_vs_index.png")

    def r07():
        fig, axes = plt.subplots(1, 3, figsize=(16, 4.5), sharey=True)
        for ax, (col, order, title) in zip(axes, (("band_google", band_order, "distance band"),
                                                  ("road_type_google", rt_order, "road type"),
                                                  ("hotspot_exposure_google", ["high", "low"], "hotspot exposure"))):
            d = m0.assign(dist=m0.lr_dist.abs(), time=m0.lr_time.abs()).melt(
                id_vars=[col], value_vars=["dist", "time"], var_name="metric", value_name="abs_log_ratio")
            sns.barplot(data=d, x=col, y="abs_log_ratio", hue="metric", order=order, estimator=np.median,
                        errorbar=("ci", 95), ax=ax)
            ax.set(title=f"r07 — |log(LLM/Google)| by {title}", xlabel="", ylabel="median |log ratio|")
        save(fig, "r07_error_by_group.png")

    def r08():
        fig, axes = plt.subplots(1, 2, figsize=(13, 4.5))
        d = m0.melt(id_vars=["road_type_google"], value_vars=["validity_share", "recall_roads", "jaccard_roads"],
                    var_name="metric", value_name="value")
        sns.barplot(data=d, x="road_type_google", y="value", hue="metric", order=rt_order, errorbar=("ci", 95), ax=axes[0])
        axes[0].set(title="r08a — Road names: validity / recall of Google's roads / Jaccard", xlabel="", ylim=(0, 1))
        axes[1].hist(m0.jaccard_roads.dropna(), bins=20, color="#577590")
        axes[1].set(title="r08b — Jaccard overlap LLM roads vs Google roads (per query)", xlabel="Jaccard")
        save(fig, "r08_road_validity_overlap.png")

    def r09():
        fig, axes = plt.subplots(1, 2, figsize=(12, 4))
        axes[0].hist(cdf.cv_km, bins=30, alpha=.6, label="distance")
        axes[0].hist(cdf.cv_min, bins=30, alpha=.6, label="time")
        axes[0].set(title="r09a — Spread over 3 samples (coefficient of variation)", xlabel="CV")
        axes[0].legend()
        axes[1].hist(cdf.roads_jaccard_between_samples.dropna(), bins=20, color="#90be6d")
        axes[1].set(title="r09b — Road-list overlap between samples (Jaccard)", xlabel="Jaccard")
        save(fig, "r09_consistency.png")

    def r10():
        d = pd.DataFrame({"LLM": m0.lr_time.abs(), "naive baseline": m0.lr_time_base.abs()})
        d2 = pd.DataFrame({"LLM": m0.lr_dist.abs(), "naive baseline": m0.lr_dist_base.abs()})
        fig, axes = plt.subplots(1, 2, figsize=(12, 4.5))
        for ax, dd, name in zip(axes, (d2, d), ("distance", "time")):
            sns.boxplot(data=dd, showfliers=False, ax=ax)
            ax.set(title=f"r10 — |log ratio| vs Google: {name}", ylabel="|log(estimate / Google)|")
        save(fig, "r10_llm_vs_baseline.png")

    def r11():
        fig, axes = plt.subplots(1, 2, figsize=(12, 4.5))
        for ax, y, name in zip(axes, ("med_abs_lr_dist", "med_abs_lr_time"), ("distance", "time")):
            sns.regplot(data=route, x="arterial_share", y=y, scatter_kws={"s": 18}, ax=ax)
            ax.set(title=f"r11 — Route-level {name} error vs main-road share (ρ = {spearman(route.arterial_share, route[y]):.2f})",
                   xlabel="share of Google route on arterial roads", ylabel="median |log ratio|")
        save(fig, "r11_error_vs_arterial_share.png")

    for fn in (r01, r02, r03, r04, r05, r06, r07, r08, r09, r10, r11):
        guarded(fn)


if __name__ == "__main__":
    main()
