"""
Step 4b (v2): Offline post-processing of the Google ground truth. NO API calls.

Input : gmaps_responses.jsonl (from 4_query_gmaps_v2.py), od_pairs.csv, candidate_pairs.csv,
        hotspot_legs.geojson, the local OSM graph.
Output: gmaps_queries.csv  — one row per query (route × day × slot)
        gmaps_routes.csv   — one row per route: FINAL tags from Google's route + stability stats
        figures/phase2/q1…q7 plots

Per query (primary route = routes[0]):
  distance, duration (with predicted traffic), staticDuration (no traffic), congestion ratio;
  endpoint offsets (Google's start/end vs our landmark coordinates, check <= 150 m);
  map-matched OSM road-name sequence (ground truth for road overlap) + arterial share;
  road names parsed from Google's step instructions (cross-check); hotspot share.
Per route: final tags from the MOST FREQUENT Google path over the 28 queries (tie -> Wednesday MID_DAY),
  change vs provisional (OSM) tags, number of distinct Google paths over the 28 queries,
  duration range, weekday/weekend peak-to-night ratios.

Usage: python 4b_process_gmaps_v2.py [--mock]
"""

import argparse
import re

import numpy as np
import pandas as pd

import config as C
from v2_common import (OsmNetwork, band_of, basemap, haversine_m, load_hotspot_union, read_jsonl,
                       road_type_of, sha1_short)

PEAKS = ("AM_PEAK", "PM_PEAK")
_STEP_ROAD = re.compile(r"\b(?:onto|on)\s+(.+?)(?:\s+toward\b|\s+Pass\b|\s+Destination\b|\n|$)")


def base_dir(mock: bool):
    return C.V2_MOCK_DIR if mock else C.V2_DIR


def step_roads(steps: list) -> list:
    """Ordered road names mentioned in Google's turn-by-turn instructions ('Turn left onto X')."""
    names = []
    for s in steps:
        for line in str(s.get("instruction", "")).split("\n"):
            m = _STEP_ROAD.search(line)
            if m:
                n = m.group(1).strip().rstrip(".")
                if n and (not names or names[-1] != n):
                    names.append(n)
    return names


def latest_ok(records: list) -> dict:
    out = {}
    for r in records:
        if r.get("status") == "ok":
            out[(r["route_id"], r["day"], r["slot_id"])] = r      # later lines win
    return out


def allowed_offset(snap_m: float) -> float:
    """Endpoint tolerance: 150 m, or the landmark's own distance to the road + 100 m for large sites (D-29)."""
    return max(C.V2_ENDPOINT_MAX_OFFSET_M, (0 if pd.isna(snap_m) else snap_m) + C.V2_ENDPOINT_EXTRA_M)


def process_queries(recs: dict, od: pd.DataFrame, net: OsmNetwork, hot_union) -> pd.DataFrame:
    odi = od.set_index("route_id")
    snap = pd.read_csv(C.V2_LANDMARKS_GEOCODED_CSV).set_index("landmark_id").snap_m
    cache = {}
    rows = []
    for i, ((rid, day, slot), rec) in enumerate(sorted(recs.items()), 1):
        rt = rec["routes"][0]
        o = odi.loc[rid]
        coords = rt["polyline"]
        key = sha1_short(str([(round(x, 5), round(y, 5)) for x, y in coords]))
        if key not in cache:                     # identical paths are matched only once
            line = net.line_to_utm(coords)
            m = net.match_line(line)
            hot = float(line.intersection(hot_union).length) if line.length else 0.0
            cache[key] = (m, hot, line.length)
        m, hot, glen = cache[key]
        s_lat, s_lng = rt["start_location"]
        e_lat, e_lng = rt["end_location"]
        start_off = float(haversine_m(o.origin_lat, o.origin_lng, s_lat, s_lng)) if s_lat is not None else np.nan
        end_off = float(haversine_m(o.dest_lat, o.dest_lng, e_lat, e_lng)) if e_lat is not None else np.nan
        start_allow, end_allow = allowed_offset(snap.get(o.origin_id)), allowed_offset(snap.get(o.dest_id))
        rows.append({
            "route_id": rid, "day": day, "slot_id": slot, "is_weekend": day in C.V2_WEEKEND_DAYS,
            "departure_ist": rec["departure_ist"],
            "distance_m": rt["distance_m"], "duration_s": rt["duration_s"], "static_duration_s": rt["static_duration_s"],
            "congestion_ratio": rt["duration_s"] / rt["static_duration_s"] if rt["static_duration_s"] else np.nan,
            "description": rt["description"], "n_routes": rec.get("n_routes", 1),
            "alt_distances_m": "|".join(str(a["distance_m"]) for a in rec["routes"][1:]),
            "start_offset_m": round(start_off, 1), "end_offset_m": round(end_off, 1),
            "start_allowed_m": round(start_allow), "end_allowed_m": round(end_allow),
            "endpoints_ok": bool(start_off <= start_allow and end_off <= end_allow),
            "path_key": key, "polyline_len_m": round(glen),
            "osm_road_seq": " | ".join(m["road_names"]), "n_osm_roads": len(m["road_names"]),
            "arterial_share_google": round(m["arterial_share"], 3), "unmatched_frac": round(m["unmatched_frac"], 3),
            "hotspot_overlap_m_google": round(hot), "hotspot_share_google": round(hot / glen, 3) if glen else 0.0,
            "google_step_roads": " | ".join(step_roads(rt["steps"])),
            "mock": rec.get("mock", False),
        })
        if i % 200 == 0:
            print(f"  processed {i}/{len(recs)} queries ({len(cache)} distinct paths)")
    return pd.DataFrame(rows)


def route_summary(q: pd.DataFrame, od: pd.DataFrame, band_medians: dict) -> pd.DataFrame:
    ref_day, ref_slot = C.V2_TAG_REFERENCE_QUERY
    out = []
    for rid, g in q.groupby("route_id"):
        prov = od.set_index("route_id").loc[rid]
        # Final tags come from the path Google chose most often over the 28 queries (D-28);
        # among queries on that path, prefer the Wednesday MID_DAY one, else the first.
        counts = g.path_key.value_counts()
        top = counts[counts == counts.max()].index
        wed = g[(g.day == ref_day) & (g.slot_id == ref_slot)]
        modal_key = wed.path_key.iloc[0] if len(wed) and wed.path_key.iloc[0] in top else sorted(top)[0]
        on_path = g[g.path_key == modal_key]
        pref = on_path[(on_path.day == ref_day) & (on_path.slot_id == ref_slot)]
        ref = pref.iloc[0] if len(pref) else on_path.iloc[0]
        band = band_of(ref.distance_m)
        rt = road_type_of(ref.arterial_share_google)
        med = band_medians.get(band, np.nan)
        exp = "high" if ref.hotspot_share_google >= med else "low"
        wk, we = g[~g.is_weekend], g[g.is_weekend]
        ratio = lambda df: (df[df.slot_id.isin(PEAKS)].duration_s.mean() / df[df.slot_id == "NIGHT"].duration_s.mean()
                            if len(df[df.slot_id == "NIGHT"]) else np.nan)
        out.append({
            "route_id": rid, "origin_name": prov.origin_name, "dest_name": prov.dest_name,
            "n_queries_ok": len(g), "reference_query": f"{ref.day} {ref.slot_id}",
            "modal_path_share": round(float(counts.max()) / len(g), 3),
            "google_distance_m": int(ref.distance_m), "osm_m_provisional": int(prov.osm_m),
            "band_google": band, "band_provisional": prov.band,
            "arterial_share_google": ref.arterial_share_google, "arterial_share_provisional": prov.arterial_share,
            "road_type_google": rt, "road_type_provisional": prov.road_type,
            "hotspot_share_google": ref.hotspot_share_google, "hotspot_band_median": med,
            "hotspot_exposure_google": exp, "hotspot_exposure_provisional": prov.hotspot_exposure,
            "group_google": f"{band}|{rt}|{exp}_hotspot" if band else None, "group_provisional": prov.group,
            "group_changed": (f"{band}|{rt}|{exp}_hotspot" != prov.group),
            "n_distinct_paths": g.path_key.nunique(),
            "duration_min_s": int(g.duration_s.min()), "duration_median_s": int(g.duration_s.median()),
            "duration_max_s": int(g.duration_s.max()),
            "peak_night_ratio_weekday": round(ratio(wk), 3), "peak_night_ratio_weekend": round(ratio(we), 3),
            "endpoints_ok_all": bool(g.endpoints_ok.all()),
            "max_endpoint_offset_m": float(np.nanmax(g[["start_offset_m", "end_offset_m"]].values)),
            "median_unmatched_frac": float(g.unmatched_frac.median()),
        })
    return pd.DataFrame(out)


# =====================================================================
#  Plots (figures/phase2/)
# =====================================================================
def make_plots(q: pd.DataFrame, r: pd.DataFrame, fig_dir):
    import matplotlib.pyplot as plt
    import seaborn as sns
    fig_dir.mkdir(parents=True, exist_ok=True)
    slots = [s["id"] for s in C.TIME_SLOTS]

    # q1 Google vs provisional OSM length
    fig, ax = plt.subplots(figsize=(7, 6))
    ax.scatter(r.osm_m_provisional / 1000, r.google_distance_m / 1000, s=20)
    mx = max(r.osm_m_provisional.max(), r.google_distance_m.max()) / 1000
    ax.plot([0, mx], [0, mx], "k:", label="equal")
    ax.set_xlabel("Provisional OSM shortest path (km)")
    ax.set_ylabel(f"Google distance, reference query (km)")
    ax.set_title("q1 — Google vs OSM route length")
    ax.legend()
    fig.savefig(fig_dir / "q1_google_vs_osm_length.png", dpi=150, bbox_inches="tight")
    plt.close(fig)

    # q2 congestion heatmap (median duration / static) by slot × day
    piv = q.pivot_table(values="congestion_ratio", index="slot_id", columns="day", aggfunc="median")
    piv = piv.reindex(index=slots, columns=C.V2_DAYS)
    fig, ax = plt.subplots(figsize=(10, 3.8))
    sns.heatmap(piv, annot=True, fmt=".2f", cmap="Reds", ax=ax)
    ax.set_title("q2 — Median congestion ratio (predicted duration / no-traffic duration)")
    fig.savefig(fig_dir / "q2_congestion_heatmap.png", dpi=150, bbox_inches="tight")
    plt.close(fig)

    # q3 median duration by slot per band, weekday vs weekend
    qq = q.merge(r[["route_id", "band_google"]], on="route_id")
    fig, axes = plt.subplots(1, 3, figsize=(15, 4), sharey=False)
    for ax, (band, _, _) in zip(axes, C.V2_BANDS):
        sub = qq[qq.band_google == band]
        for wkend, lab in ((False, "weekday"), (True, "weekend")):
            m = sub[sub.is_weekend == wkend].groupby("slot_id").duration_s.median().reindex(slots) / 60
            ax.plot(slots, m.values, marker="o", label=lab)
        ax.set_title(f"q3 — {band} (n={sub.route_id.nunique()} routes)")
        ax.set_ylabel("median predicted duration (min)")
        ax.legend()
    fig.savefig(fig_dir / "q3_duration_by_slot_band.png", dpi=150, bbox_inches="tight")
    plt.close(fig)

    # q4 tag changes provisional -> Google
    changes = {"band": (r.band_google != r.band_provisional).sum(),
               "road type": (r.road_type_google != r.road_type_provisional).sum(),
               "hotspot exposure": (r.hotspot_exposure_google != r.hotspot_exposure_provisional).sum(),
               "any (group)": r.group_changed.sum()}
    fig, axes = plt.subplots(1, 2, figsize=(13, 4.5))
    axes[0].bar(changes.keys(), changes.values(), color="#e76f51")
    axes[0].set_title(f"q4a — Routes whose tag changed (of {len(r)})")
    fill = r.groupby(["band_google", "road_type_google"]).size().unstack(fill_value=0)
    sns.heatmap(fill, annot=True, fmt="d", cmap="Blues", ax=axes[1])
    axes[1].set_title("q4b — Routes per band × road type (Google tags)")
    fig.savefig(fig_dir / "q4_tag_changes.png", dpi=150, bbox_inches="tight")
    plt.close(fig)

    # q5 endpoint offsets
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.hist(np.concatenate([q.start_offset_m.dropna(), q.end_offset_m.dropna()]), bins=40, color="#577590")
    ax.axvline(C.V2_ENDPOINT_MAX_OFFSET_M, color="red", ls="--", label=f"base limit {C.V2_ENDPOINT_MAX_OFFSET_M} m (large sites: snap + {C.V2_ENDPOINT_EXTRA_M} m)")
    ax.set_xlabel("distance Google start/end ↔ our landmark coordinate (m)")
    ax.set_title(f"q5 — Endpoint offsets ({(~q.endpoints_ok).sum()} of {len(q)} queries outside tolerance)")
    ax.legend()
    fig.savefig(fig_dir / "q5_endpoint_offsets.png", dpi=150, bbox_inches="tight")
    plt.close(fig)

    # q6 route-choice stability
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.hist(r.n_distinct_paths, bins=range(1, int(r.n_distinct_paths.max()) + 2), align="left", color="#90be6d")
    ax.set_xlabel("distinct Google paths over the 28 queries")
    ax.set_ylabel("routes")
    ax.set_title("q6 — Does Google change its path with time of day?")
    fig.savefig(fig_dir / "q6_path_stability.png", dpi=150, bbox_inches="tight")
    plt.close(fig)

    # q7 peak / night ratio
    fig, ax = plt.subplots(figsize=(8, 4.5))
    long = r.melt(id_vars="band_google", value_vars=["peak_night_ratio_weekday", "peak_night_ratio_weekend"],
                  var_name="days", value_name="ratio")
    sns.boxplot(data=long, x="band_google", y="ratio", hue="days", ax=ax)
    ax.axhline(1, color="k", ls=":")
    ax.set_title("q7 — Google peak / night duration ratio (the time-of-day signal the LLM should reproduce)")
    fig.savefig(fig_dir / "q7_peak_night_ratio.png", dpi=150, bbox_inches="tight")
    plt.close(fig)


# =====================================================================
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--mock", action="store_true", help="process data/benchmark_v2/mock/gmaps/ instead")
    args = ap.parse_args()
    bd = base_dir(args.mock)
    gdir = bd / "gmaps"
    recs = latest_ok(read_jsonl(gdir / C.V2_GMAPS_RESPONSES_JSONL))
    od = pd.read_csv(C.V2_OD_PAIRS_CSV)
    expected = len(od) * len(C.V2_DAYS) * len(C.TIME_SLOTS)
    print(f"OK queries: {len(recs)} of {expected}{'  [MOCK]' if args.mock else ''}")
    if not recs:
        raise SystemExit("No OK Google responses yet — run 4_query_gmaps_v2.py first.")

    cand = pd.read_csv(C.V2_CANDIDATE_PAIRS_CSV)
    band_medians = cand[cand.eligible].groupby("band").hotspot_share.median().to_dict()
    hot_union, _ = load_hotspot_union()
    net = OsmNetwork()

    q = process_queries(recs, od, net, hot_union)
    q.to_csv(gdir / C.V2_GMAPS_QUERIES_CSV, index=False)
    r = route_summary(q, od, band_medians)
    r.to_csv(gdir / C.V2_GMAPS_ROUTES_CSV, index=False)
    print(f"Saved {gdir / C.V2_GMAPS_QUERIES_CSV} ({len(q)} rows) and {gdir / C.V2_GMAPS_ROUTES_CSV} ({len(r)} rows)")

    print(f"Endpoints within tolerance (150 m, or snap+100 m for large sites): {q.endpoints_ok.mean():.1%} of queries "
          f"(routes with any offset issue: {(~r.endpoints_ok_all).sum()})")
    print(f"Map-matching: median unmatched fraction {q.unmatched_frac.median():.1%}")
    print(f"Routes whose group changed (provisional -> Google): {int(r.group_changed.sum())} of {len(r)}")
    print(f"Routes where Google used >1 distinct path over 28 queries: {(r.n_distinct_paths > 1).sum()}")
    fig_dir = bd / "figures" / "phase2"
    make_plots(q, r, fig_dir)
    print(f"Figures -> {fig_dir}")


if __name__ == "__main__":
    main()
