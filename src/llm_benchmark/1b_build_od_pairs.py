"""
Step 1b (v2): Build the benchmark route list (origin-destination pairs).

Subcommands
-----------
  legs                     Offline. Extract Stage-4 leg geometries from raw Stage-2 JSON,
                           keep plausible legs, mark hotspots (top CV of live duration).
                           -> data/benchmark_v2/hotspot_legs.geojson (+ plot 3)

  geocode [--dry-run]      PAID (Google Places Text Search). Landmark name -> coordinate,
          [--only L01,L02] with automatic checks. Responses are cached, so reruns of
          [--provider ...]  unchanged rows cost nothing. --dry-run makes NO network calls.
                           -> landmarks_geocoded.csv, landmarks_review.csv (+ plots 1, 2)

  pairs [--source approx|geocoded]
                           Offline. OSM shortest path for every candidate pair, tags
                           (band, road type, hotspot), balanced selection, outputs + plots.
                           --source approx = rehearsal on the seed's approximate coordinates
                           (written to data/benchmark_v2/rehearsal_approx/, never used in results).

Definitions and thresholds: docs/benchmark_v2/METHODOLOGY.md, values in config.py (V2 section).
"""

import argparse
import hashlib
import json
import math
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

import config as C

from v2_common import (LAT_LNG_CRS, OsmNetwork, band_of, basemap as _basemap, friendly_api_error,
                       haversine_m, load_env_key, road_type_of, stable_hash, token_set_ratio)


# =====================================================================
#  Subcommand: legs  (offline)
# =====================================================================
def cmd_legs(args):
    import geopandas as gpd
    from shapely.geometry import LineString
    sys.path.insert(0, str(C._PROJECT_ROOT / "src" / "pipeline"))
    from data_pipeline import generate_sub_route_id  # reuse Stage-3 leg hashing

    master = pd.read_csv(C.MASTER_SUBROUTES_CSV)
    flat = pd.read_csv(C.FLATTENED_TRAFFIC_CSV)

    stats = flat.groupby("sub_route_id").agg(
        snapshot_count=("live_duration_s", "size"),
        mean_live_s=("live_duration_s", "mean"),
        std_live_s=("live_duration_s", "std"),
        road_name=("road_name", "first"),
    ).reset_index()
    stats["cv_live"] = stats["std_live_s"] / stats["mean_live_s"]
    legs = master.merge(stats, on="sub_route_id", how="left")

    lat0, lat1, lng0, lng1 = C.V2_LEG_BBOX
    straight = haversine_m(legs.start_lat, legs.start_lng, legs.end_lat, legs.end_lng)
    legs["straight_m"] = straight
    legs["in_bbox"] = (legs.start_lat.between(lat0, lat1) & legs.end_lat.between(lat0, lat1)
                       & legs.start_lng.between(lng0, lng1) & legs.end_lng.between(lng0, lng1))
    legs["detour"] = legs.distance_meters / np.maximum(straight, 1)
    legs["plausible"] = (legs.in_bbox & (legs.detour <= C.V2_LEG_MAX_DETOUR)
                         & (legs.snapshot_count >= C.V2_LEG_MIN_SNAPSHOTS))
    plaus = legs[legs.plausible].copy()
    cut = plaus.cv_live.quantile(1 - C.V2_HOTSPOT_TOP_FRACTION)
    plaus["is_hotspot"] = plaus.cv_live >= cut
    print(f"Legs: {len(legs)} total, {len(plaus)} plausible, {int(plaus.is_hotspot.sum())} hotspots "
          f"(CV >= {cut:.3f})")

    # Geometry: first raw snapshot in which each plausible leg appears
    need = set(plaus.sub_route_id)
    geoms = {}
    files = sorted(C.RAW_GMAPS_DIR.glob("bangalore_routes_response_*.json"))
    for f in files:
        with open(f, encoding="utf-8") as fh:
            records = json.load(fh)
        for rec in records:
            for route in (rec.get("api_response") or {}).get("routes", []):
                for leg in route.get("legs", []):
                    coords = leg.get("polyline", {}).get("geoJsonLinestring", {}).get("coordinates", [])
                    if len(coords) < 2:
                        continue
                    lid = generate_sub_route_id(coords[0][1], coords[0][0], coords[-1][1], coords[-1][0])
                    if lid in need and lid not in geoms:
                        geoms[lid] = LineString(coords)
        print(f"  scanned {f.name}: geometries {len(geoms)}/{len(need)}")
        if len(geoms) == len(need):
            break

    plaus["geometry"] = plaus.sub_route_id.map(geoms)
    missing = plaus.geometry.isna().sum()
    if missing:
        print(f"  WARNING: {missing} plausible legs had no geometry in raw JSON; they are dropped")
    plaus = plaus[plaus.geometry.notna()]
    gdf = gpd.GeoDataFrame(plaus, geometry="geometry", crs=LAT_LNG_CRS)
    cols = ["sub_route_id", "road_name", "distance_meters", "straight_m", "detour", "snapshot_count",
            "mean_live_s", "std_live_s", "cv_live", "is_hotspot", "geometry"]
    C.V2_DIR.mkdir(parents=True, exist_ok=True)
    gdf[cols].to_file(C.V2_HOTSPOT_LEGS_GEOJSON, driver="GeoJSON")
    print(f"Saved {len(gdf)} legs ({int(gdf.is_hotspot.sum())} hotspots) -> {C.V2_HOTSPOT_LEGS_GEOJSON}")

    plot_hotspot_legs(gdf, cut)


# =====================================================================
#  Subcommand: geocode  (PAID unless cached / --dry-run)
# =====================================================================
def _cache_path(provider: str, query: str) -> Path:
    h = hashlib.sha1(f"{provider}|{query}".encode()).hexdigest()[:16]
    return C.V2_CACHE_DIR / provider / f"{h}.json"


def _places_search(query: str, api_key: str) -> dict:
    import requests
    body = {
        "textQuery": query,
        "pageSize": C.V2_PLACES_RESULTS,
        "languageCode": "en",
        "regionCode": "IN",
        "locationRestriction": {"rectangle": C.V2_BBOX},
    }
    headers = {"Content-Type": "application/json", "X-Goog-Api-Key": api_key,
               "X-Goog-FieldMask": C.PLACES_FIELD_MASK}
    r = requests.post(C.PLACES_TEXT_SEARCH_URL, headers=headers, json=body, timeout=30)
    if r.status_code != 200:
        return {"_error": friendly_api_error(r.status_code, r.text), "_status": r.status_code}
    results = []
    for p in r.json().get("places", []):
        results.append({
            "place_id": p.get("id"),
            "name": (p.get("displayName") or {}).get("text", ""),
            "formatted_address": p.get("formattedAddress", ""),
            "lat": p["location"]["latitude"], "lng": p["location"]["longitude"],
            "types": p.get("types", []), "primary_type": p.get("primaryType", ""),
        })
    return {"results": results}


def _geocoding_search(query: str, api_key: str) -> dict:
    import requests
    b = C.V2_BBOX
    params = {"address": query, "key": api_key, "components": "country:IN",
              "bounds": f"{b['low']['latitude']},{b['low']['longitude']}|"
                        f"{b['high']['latitude']},{b['high']['longitude']}"}
    r = requests.get(C.GEOCODING_URL, params=params, timeout=30)
    data = r.json() if r.status_code == 200 else {}
    if r.status_code != 200 or data.get("status") not in ("OK", "ZERO_RESULTS"):
        return {"_error": friendly_api_error(r.status_code, json.dumps(data) or r.text),
                "_status": r.status_code}
    results = []
    for g in data.get("results", [])[: C.V2_PLACES_RESULTS]:
        loc = g["geometry"]["location"]
        results.append({"place_id": g.get("place_id"), "name": g["formatted_address"].split(",")[0],
                        "formatted_address": g["formatted_address"], "lat": loc["lat"], "lng": loc["lng"],
                        "types": g.get("types", []), "primary_type": (g.get("types") or [""])[0]})
    return {"results": results}


def cmd_geocode(args):
    seed = pd.read_csv(C.V2_LANDMARKS_SEED_CSV)
    if args.only:
        wanted = set(args.only.split(","))
        todo = seed[seed.landmark_id.isin(wanted)]
    else:
        todo = seed
    provider = args.provider
    uncached = [q for q in todo.search_query if not _cache_path(provider, q).exists()]

    print(f"Landmarks in seed: {len(seed)} | selected: {len(todo)} | provider: {provider}")
    print(f"Cached already: {len(todo) - len(uncached)} | NEW API calls needed: {len(uncached)}")
    price = C.V2_PLACES_PRICE_PER_CALL if provider == "places" else 0.005
    print(f"Estimated cost if beyond free monthly cap: ${len(uncached) * price:.2f} "
          f"(free cap: 5,000 Places Pro / 10,000 Geocoding calls per month -> expected $0)")
    if args.dry_run:
        print("DRY RUN — no network calls made.")
        return

    api_key = load_env_key(C.GMAPS_API_KEY_ENV)
    search = _places_search if provider == "places" else _geocoding_search
    calls = 0
    for _, row in todo.iterrows():
        cp = _cache_path(provider, row.search_query)
        if cp.exists():
            continue
        resp = search(row.search_query, api_key)
        calls += 1
        if "_error" in resp:
            # Stop on the first error: config problems (billing/API disabled) affect every call.
            print(f"  {row.landmark_id}: API error -> {resp['_error']}")
            print(f"Stopped after {calls} call(s); nothing cached for the failed row.")
            return
        cp.parent.mkdir(parents=True, exist_ok=True)
        resp.update({"query": row.search_query, "provider": provider,
                     "fetched_at": pd.Timestamp.now(tz="Asia/Kolkata").isoformat()})
        cp.write_text(json.dumps(resp, indent=1), encoding="utf-8")
        print(f"  {row.landmark_id}: {len(resp['results'])} result(s)")
        time.sleep(0.1)
    print(f"API calls made: {calls}")
    evaluate_geocodes(seed, provider)


def evaluate_geocodes(seed: pd.DataFrame, provider: str):
    """Apply METHODOLOGY §2 checks to cached responses; write geocoded + review CSVs and plots."""
    net = OsmNetwork()
    rows = []
    for _, s in seed.iterrows():
        cp = _cache_path(provider, s.search_query)
        base = s.to_dict()
        if not cp.exists():
            rows.append({**base, "status": "NOT_QUERIED", "flags": "not queried yet"})
            continue
        results = json.loads(cp.read_text(encoding="utf-8")).get("results", [])
        if not results:
            rows.append({**base, "status": "FLAG", "flags": "no_results"})
            continue
        top = results[0]
        name_score = token_set_ratio(s.llm_name, top["name"])
        approx_d = float(haversine_m(s.rough_lat, s.rough_lng, top["lat"], top["lng"]))
        area_in_addr = str(s.expected_area).lower() in top["formatted_address"].lower()
        area_ok = area_in_addr or approx_d <= C.V2_APPROX_MAX_M
        others = [r for r in results[1:] if token_set_ratio(s.llm_name, r["name"]) >= C.V2_NAME_SCORE_MIN]
        amb_d = max([float(haversine_m(top["lat"], top["lng"], r["lat"], r["lng"])) for r in others],
                    default=0.0)
        ambiguous = amb_d > C.V2_AMBIGUITY_M
        type_ok = top["primary_type"] not in C.V2_AREA_TYPES and not set(top["types"]) <= C.V2_AREA_TYPES
        snap_m = float(net.nearest_edge_dist(top["lat"], top["lng"]))

        flags = []
        if name_score < C.V2_NAME_SCORE_MIN:
            flags.append(f"name_score={name_score:.0f}")
        if not area_ok:
            flags.append("area_mismatch")
        if approx_d > C.V2_APPROX_MAX_M:
            flags.append(f"far_from_approx={approx_d / 1000:.1f}km")
        if ambiguous:
            flags.append(f"ambiguous(2nd match {amb_d / 1000:.1f}km away)")
        if not type_ok:
            flags.append(f"area_type={top['primary_type']}")
        if snap_m > C.V2_SNAP_MAX_M:
            flags.append(f"snap={snap_m:.0f}m")

        rows.append({**base, "lat": top["lat"], "lng": top["lng"], "place_id": top["place_id"],
                     "returned_name": top["name"], "formatted_address": top["formatted_address"],
                     "primary_type": top["primary_type"], "n_results": len(results),
                     "name_score": round(name_score, 1), "area_in_address": area_in_addr,
                     "approx_dist_m": round(approx_d), "ambiguity_m": round(amb_d),
                     "snap_m": round(snap_m, 1), "status": "OK" if not flags else "FLAG",
                     "flags": "; ".join(flags)})
    out = pd.DataFrame(rows)

    # Human review decisions (Gate 2) live in review_decisions.csv so re-running the checks
    # never loses them: APPROVE turns a FLAG into APPROVED; DROP excludes the landmark.
    out["review_decision"], out["review_reason"] = "", ""
    if C.V2_REVIEW_DECISIONS_CSV.exists():
        dec = pd.read_csv(C.V2_REVIEW_DECISIONS_CSV).set_index("landmark_id")
        for i, r in out.iterrows():
            if r.landmark_id not in dec.index:
                continue
            d = dec.loc[r.landmark_id]
            out.at[i, "review_decision"], out.at[i, "review_reason"] = d.decision, d.reason
            if d.decision == "DROP":
                out.at[i, "status"] = "DROPPED"
            elif d.decision == "APPROVE" and r.status == "FLAG":
                out.at[i, "status"] = "APPROVED"
    out.to_csv(C.V2_LANDMARKS_GEOCODED_CSV, index=False)
    out[out.status != "OK"].to_csv(C.V2_LANDMARKS_REVIEW_CSV, index=False)
    print(out.status.value_counts().to_string())
    unresolved = out[out.status.isin(["FLAG", "NOT_QUERIED"])]
    if len(unresolved):
        print(f"UNRESOLVED (need review): {', '.join(unresolved.landmark_id)}")
    print(f"Saved {C.V2_LANDMARKS_GEOCODED_CSV.name} and {C.V2_LANDMARKS_REVIEW_CSV.name}")
    fig_dir = C.V2_FIGURES_DIR / "phase1"
    plot_landmarks(out, fig_dir, net, title_suffix="geocoded")
    plot_geocode_quality(out, fig_dir)


# =====================================================================
#  Subcommand: pairs  (offline)
# =====================================================================
def load_landmarks(source: str) -> pd.DataFrame:
    if source == "approx":
        lm = pd.read_csv(C.V2_LANDMARKS_SEED_CSV)
        lm["lat"], lm["lng"], lm["place_id"] = lm.rough_lat, lm.rough_lng, ""
        lm["status"] = "APPROX"
        return lm
    if not C.V2_LANDMARKS_GEOCODED_CSV.exists():
        sys.exit("landmarks_geocoded.csv not found — run `geocode` first (or use --source approx).")
    lm = pd.read_csv(C.V2_LANDMARKS_GEOCODED_CSV)
    keep = lm.status.isin(["OK", "APPROVED"])
    print(f"Using {keep.sum()} landmarks with status OK/APPROVED (skipping {(~keep).sum()} flagged)")
    return lm[keep].copy()


def route_paths(net: OsmNetwork, lm: pd.DataFrame, pairs: list) -> dict:
    """OSM shortest path (by length) for each (origin_id, dest_id). One Dijkstra per origin."""
    import networkx as nx
    node_of = {r.landmark_id: net.nearest_node(r.lat, r.lng)[0] for r in lm.itertuples()}
    by_origin = {}
    for o, d in pairs:
        by_origin.setdefault(o, []).append(d)
    paths = {}
    cutoff = C.V2_BANDS[-1][2] * 1.3
    for i, (o, dests) in enumerate(sorted(by_origin.items()), 1):
        pred, dist = nx.dijkstra_predecessor_and_distance(net.G, node_of[o], cutoff=cutoff, weight="length")
        for d in dests:
            tgt = node_of[d]
            if tgt not in dist:
                paths[(o, d)] = None
                continue
            path, n = [tgt], tgt
            while n != node_of[o]:
                n = pred[n][0]
                path.append(n)
            paths[(o, d)] = path[::-1]
        print(f"  routed origin {i}/{len(by_origin)} ({o}: {len(dests)} destinations)", end="\r")
    print()
    return paths


def describe_path(net: OsmNetwork, path: list, hotspot_union):
    from shapely.geometry import LineString
    total, arterial, names = 0.0, 0.0, []
    for u, v in zip(path[:-1], path[1:]):
        e = net.best_edge(u, v)
        length = float(e.get("length", 0))
        hw = e.get("highway")
        hw = hw[0] if isinstance(hw, list) else hw
        total += length
        if hw in C.V2_ARTERIAL_HIGHWAYS:
            arterial += length
        nm = e.get("name")
        for n in (nm if isinstance(nm, list) else [nm]):
            if isinstance(n, str) and n and (not names or names[-1] != n):
                names.append(n)
    line = LineString([net.node_xy[n] for n in path]) if len(path) > 1 else None
    overlap = float(line.intersection(hotspot_union).length) if (line is not None and hotspot_union) else 0.0
    return total, (arterial / total if total else 0.0), names, overlap, line


def select_routes(cand: pd.DataFrame, lm: pd.DataFrame) -> pd.DataFrame:
    """Round-robin balanced selection over the 18 groups (METHODOLOGY §4)."""
    pos = lm.set_index("landmark_id")[["lat", "lng"]]
    elig = cand[cand.eligible].copy()
    elig["order"] = [stable_hash(o, d) for o, d in zip(elig.origin_id, elig.dest_id)]
    queues = {g: df.sort_values("order").to_dict("records") for g, df in elig.groupby("group")}
    uses, chosen, per_group = {}, [], {g: 0 for g in queues}

    def near_dup(r):
        for s in chosen:
            for a, b in ((s["origin_id"], s["dest_id"]), (s["dest_id"], s["origin_id"])):
                if (haversine_m(*pos.loc[r["origin_id"]], *pos.loc[a]) < C.V2_NEAR_DUP_M and
                        haversine_m(*pos.loc[r["dest_id"]], *pos.loc[b]) < C.V2_NEAR_DUP_M):
                    return True
        return False

    progress = True
    while progress and len(chosen) < C.V2_TARGET_ROUTES:
        progress = False
        for g in sorted(queues, key=lambda g: (per_group[g], g)):
            if per_group[g] >= C.V2_MAX_PER_GROUP or len(chosen) >= C.V2_TARGET_ROUTES:
                continue
            q = queues[g]
            while q:
                r = q.pop(0)
                if uses.get(r["origin_id"], 0) >= C.V2_MAX_LANDMARK_USES:
                    continue
                if uses.get(r["dest_id"], 0) >= C.V2_MAX_LANDMARK_USES:
                    continue
                if near_dup(r):
                    continue
                chosen.append(r)
                per_group[g] += 1
                uses[r["origin_id"]] = uses.get(r["origin_id"], 0) + 1
                uses[r["dest_id"]] = uses.get(r["dest_id"], 0) + 1
                progress = True
                break
    sel = pd.DataFrame(chosen).drop(columns=["order"])
    sel.insert(0, "route_id", [f"R{i:03d}" for i in range(1, len(sel) + 1)])
    return sel


def cmd_pairs(args):
    import geopandas as gpd
    from shapely.ops import unary_union

    out_dir = C.V2_REHEARSAL_DIR if args.source == "approx" else C.V2_DIR
    fig_dir = (C.V2_REHEARSAL_DIR if args.source == "approx" else C.V2_FIGURES_DIR) / "figures_phase1" \
        if args.source == "approx" else C.V2_FIGURES_DIR / "phase1"
    out_dir.mkdir(parents=True, exist_ok=True)
    if args.source == "approx":
        print("REHEARSAL on approximate coordinates — outputs are NOT benchmark data.")

    lm = load_landmarks(args.source).reset_index(drop=True)
    net = OsmNetwork()

    # Hotspot union (UTM, buffered)
    if not C.V2_HOTSPOT_LEGS_GEOJSON.exists():
        sys.exit("hotspot_legs.geojson missing — run `legs` first.")
    legs = gpd.read_file(C.V2_HOTSPOT_LEGS_GEOJSON).to_crs(C.UTM_CRS)
    hot = legs[legs.is_hotspot]
    hotspot_union = unary_union(hot.geometry.buffer(C.V2_HOTSPOT_BUFFER_M).tolist())
    print(f"Hotspot legs: {len(hot)} (buffer {C.V2_HOTSPOT_BUFFER_M} m)")

    # Candidate pairs (one deterministic direction per unordered pair)
    ids = lm.landmark_id.tolist()
    P = lm.set_index("landmark_id")
    pairs = []
    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            d = float(haversine_m(P.at[a, "lat"], P.at[a, "lng"], P.at[b, "lat"], P.at[b, "lng"]))
            if C.V2_PAIR_MIN_STRAIGHT_M <= d <= C.V2_PAIR_MAX_STRAIGHT_M:
                pairs.append((a, b) if stable_hash(a, b) % 2 == 0 else (b, a))
    print(f"Candidate pairs (straight line {C.V2_PAIR_MIN_STRAIGHT_M / 1000}-"
          f"{C.V2_PAIR_MAX_STRAIGHT_M / 1000} km): {len(pairs)}")

    paths = route_paths(net, lm, pairs)
    rows, lines = [], {}
    for o, d in pairs:
        path = paths.get((o, d))
        straight = float(haversine_m(P.at[o, "lat"], P.at[o, "lng"], P.at[d, "lat"], P.at[d, "lng"]))
        base = {"origin_id": o, "origin_name": P.at[o, "llm_name"], "origin_lat": P.at[o, "lat"],
                "origin_lng": P.at[o, "lng"], "origin_place_id": P.at[o, "place_id"],
                "origin_kind": P.at[o, "kind"], "origin_zone": P.at[o, "zone"],
                "dest_id": d, "dest_name": P.at[d, "llm_name"], "dest_lat": P.at[d, "lat"],
                "dest_lng": P.at[d, "lng"], "dest_place_id": P.at[d, "place_id"],
                "dest_kind": P.at[d, "kind"], "dest_zone": P.at[d, "zone"], "straight_m": round(straight)}
        if not path or len(path) < 2:
            rows.append({**base, "eligible": False, "ineligible_reason": "no_osm_path"})
            continue
        length, share, names, overlap, line = describe_path(net, path, hotspot_union)
        band = band_of(length)
        compact_ok = length >= C.V2_SHORT_ROUTE_M or (
            P.at[o, "kind"] in C.V2_COMPACT_KINDS and P.at[d, "kind"] in C.V2_COMPACT_KINDS)
        reason = "" if band and compact_ok else ("outside_bands" if not band else "short_non_compact")
        rows.append({**base, "osm_m": round(length), "detour": round(length / max(straight, 1), 3),
                     "band": band, "arterial_share": round(share, 3), "road_type": road_type_of(share),
                     "hotspot_overlap_m": round(overlap),
                     "hotspot_share": round(overlap / length, 3) if length else 0.0,
                     "osm_road_names": " | ".join(names), "eligible": not reason,
                     "ineligible_reason": reason})
        lines[(o, d)] = line
    cand = pd.DataFrame(rows)
    cand["coord_source"] = args.source

    # Hotspot exposure is RELATIVE: high if the route's hotspot share is >= the median share of
    # eligible candidates in the same band (METHODOLOGY §3, DECISIONS D-17). The absolute
    # ">= 300 m overlap" rule marked ~98 % of candidates as crossing, because hotspot legs
    # cover most arterial corridors.
    med = cand[cand.eligible].groupby("band").hotspot_share.median()
    cand["hotspot_band_median"] = cand.band.map(med)
    cand["hotspot_exposure"] = np.where(cand.hotspot_share >= cand.hotspot_band_median, "high", "low")
    cand["group"] = np.where(cand.band.notna(),
                             cand.band.astype(str) + "|" + cand.road_type.astype(str) + "|"
                             + cand.hotspot_exposure + "_hotspot", None)
    print("Band medians of hotspot share:", med.round(3).to_dict())
    cand.to_csv(out_dir / C.V2_CANDIDATE_PAIRS_CSV.name, index=False)
    print(f"Candidates: {len(cand)} | eligible: {int(cand.eligible.sum())} | "
          f"reasons: {cand[~cand.eligible].ineligible_reason.value_counts().to_dict()}")

    sel = select_routes(cand, lm)
    sel.to_csv(out_dir / C.V2_OD_PAIRS_CSV.name, index=False)
    print(f"Selected routes: {len(sel)} (target {C.V2_TARGET_ROUTES}) -> {out_dir / C.V2_OD_PAIRS_CSV.name}")

    # GeoJSON for QGIS: selected routes (lat/lng)
    from shapely.ops import transform
    def to_ll(geom):
        return transform(lambda x, y, z=None: net.to_ll.transform(x, y), geom)
    gsel = gpd.GeoDataFrame(sel.copy(), geometry=[to_ll(lines[(o, d)]) for o, d in zip(sel.origin_id, sel.dest_id)],
                            crs=LAT_LNG_CRS)
    gsel.to_file(out_dir / C.V2_OD_PAIRS_GEOJSON.name, driver="GeoJSON")

    print_group_table(cand, sel)
    plot_pairs(cand, sel, gsel, lm, legs.to_crs(LAT_LNG_CRS), net, fig_dir)
    print(f"Figures -> {fig_dir}")


def print_group_table(cand, sel):
    groups = [f"{b[0]}|{rt}|{h}" for b in C.V2_BANDS for rt in ("arterial", "mixed", "sub_arterial")
              for h in ("high_hotspot", "low_hotspot")]
    avail = cand[cand.eligible].group.value_counts()
    got = sel.group.value_counts()
    print(f"\n{'group':38s} {'eligible':>8s} {'selected':>8s}")
    for g in groups:
        print(f"{g:38s} {avail.get(g, 0):8d} {got.get(g, 0):8d}")


# =====================================================================
#  Plots (Phase 1) — numbering matches the plan / METHODOLOGY
# =====================================================================
def plot_landmarks(lm, fig_dir, net, title_suffix=""):
    import matplotlib.pyplot as plt
    fig_dir.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(11, 11))
    _basemap(ax, net)
    pts = lm.assign(plat=lm["lat"] if "lat" in lm else lm.rough_lat,
                    plng=lm["lng"] if "lng" in lm else lm.rough_lng)
    for kind, grp in pts.groupby("kind"):
        ax.scatter(grp.plng, grp.plat, s=40, label=kind, zorder=3)
    if "status" in lm:
        fl = lm[lm.status.isin(["FLAG", "DROPPED"])]
        ax.scatter(fl["lng"], fl["lat"], s=160, facecolors="none", edgecolors="red", lw=1.5,
                   label="FLAGGED / DROPPED", zorder=4)
    for r in pts.itertuples():
        ax.annotate(r.landmark_id, (r.plng, r.plat), fontsize=7, xytext=(3, 3), textcoords="offset points")
    ax.legend(loc="upper right", fontsize=8)
    ax.set_title(f"Plot 1 — Landmarks by kind ({title_suffix})")
    fig.savefig(fig_dir / "p1_landmarks_map.png", dpi=150, bbox_inches="tight")
    plt.close(fig)


def plot_geocode_quality(lm, fig_dir):
    import matplotlib.pyplot as plt
    q = lm[lm.status.isin(["OK", "FLAG", "APPROVED", "DROPPED"]) & lm.lat.notna()]
    checks = {
        "name_score": q.name_score >= C.V2_NAME_SCORE_MIN,
        "area": q.area_in_address | (q.approx_dist_m <= C.V2_APPROX_MAX_M),
        "near_approx": q.approx_dist_m <= C.V2_APPROX_MAX_M,
        "unambiguous": q.ambiguity_m <= C.V2_AMBIGUITY_M,
        "point_type": ~q["flags"].fillna("").str.contains("area_type"),
        "snap": q.snap_m <= C.V2_SNAP_MAX_M,
    }
    fig, axes = plt.subplots(1, 2, figsize=(13, 4.5))
    passed = [int(v.sum()) for v in checks.values()]
    failed = [len(q) - p for p in passed]
    axes[0].bar(checks.keys(), passed, label="pass", color="#4c9a5a")
    axes[0].bar(checks.keys(), failed, bottom=passed, label="flag", color="#d1495b")
    axes[0].set_title("Plot 2a — Geocode checks (pass / flag)")
    axes[0].legend()
    axes[0].tick_params(axis="x", rotation=30)
    axes[1].hist(q.snap_m, bins=30, color="#577590")
    axes[1].axvline(C.V2_SNAP_MAX_M, color="red", ls="--", label=f"limit {C.V2_SNAP_MAX_M} m")
    axes[1].set_title("Plot 2b — Distance to nearest drivable OSM road")
    axes[1].set_xlabel("metres")
    axes[1].legend()
    fig.savefig(fig_dir / "p2_geocode_quality.png", dpi=150, bbox_inches="tight")
    plt.close(fig)


def plot_hotspot_legs(gdf, cut):
    import matplotlib.pyplot as plt
    fig_dir = C.V2_FIGURES_DIR / "phase1"
    fig_dir.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(11, 11))
    cold = gdf[~gdf.is_hotspot]
    hot = gdf[gdf.is_hotspot]
    cold.plot(ax=ax, column="cv_live", cmap="Greys", lw=0.8, vmin=0, vmax=cut * 1.5)
    hot.plot(ax=ax, color="red", lw=1.8, label=f"hotspot (top {int(C.V2_HOTSPOT_TOP_FRACTION * 100)}% CV)")
    ax.set_aspect(1 / math.cos(math.radians(12.97)))
    ax.set_title(f"Plot 3 — Plausible Stage-4 legs ({len(gdf)}), hotspots in red ({len(hot)}; CV ≥ {cut:.2f})")
    ax.legend()
    fig.savefig(fig_dir / "p3_hotspot_legs_map.png", dpi=150, bbox_inches="tight")
    plt.close(fig)


def plot_pairs(cand, sel, gsel, lm, legs_ll, net, fig_dir):
    import matplotlib.pyplot as plt
    import seaborn as sns
    fig_dir.mkdir(parents=True, exist_ok=True)
    band_colors = {b[0]: c for b, c in zip(C.V2_BANDS, ["#2a9d8f", "#e9c46a", "#e76f51"])}

    # Plot 1 (landmarks used in this run)
    plot_landmarks(lm, fig_dir, net, title_suffix=str(cand.coord_source.iloc[0]))

    # Plot 4 — selected routes map
    fig, ax = plt.subplots(figsize=(12, 12))
    _basemap(ax, net)
    legs_ll[legs_ll.is_hotspot].plot(ax=ax, color="red", lw=2.5, alpha=0.25, zorder=1)
    for r in gsel.itertuples():
        xs, ys = r.geometry.xy
        ax.plot(xs, ys, color=band_colors[r.band], lw=1.6, ls="--" if r.hotspot_exposure == "high" else "-", zorder=2)
    ax.scatter(lm.lng, lm.lat, s=18, color="black", zorder=3)
    for b, c in band_colors.items():
        ax.plot([], [], color=c, lw=2, label=b)
    ax.plot([], [], color="grey", ls="--", label="high hotspot exposure")
    ax.plot([], [], color="red", lw=4, alpha=0.25, label="hotspot legs")
    ax.legend(loc="upper right")
    ax.set_title(f"Plot 4 — Selected routes ({len(sel)}), provisional OSM paths")
    fig.savefig(fig_dir / "p4_selected_routes_map.png", dpi=150, bbox_inches="tight")
    plt.close(fig)

    # Plot 5 — group fill heatmaps (eligible vs selected)
    fig, axes = plt.subplots(1, 2, figsize=(14, 4.5))
    for ax, h in zip(axes, ("high_hotspot", "low_hotspot")):
        sub = sel[sel.group.str.endswith(h)]
        el = cand[cand.eligible & cand.group.fillna("").str.endswith(h)]
        tab = pd.crosstab(sub.band, sub.road_type).reindex(index=[b[0] for b in C.V2_BANDS],
                                                          columns=["arterial", "mixed", "sub_arterial"],
                                                          fill_value=0)
        etab = pd.crosstab(el.band, el.road_type).reindex_like(tab).fillna(0).astype(int)
        annot = tab.astype(str) + "\n(of " + etab.astype(str) + ")"
        sns.heatmap(tab, annot=annot, fmt="", cmap="Blues", ax=ax, cbar=False, vmin=0, vmax=C.V2_MAX_PER_GROUP)
        ax.set_title(f"Plot 5 — selected (eligible) — {h.replace('_', ' ')} exposure")
    fig.savefig(fig_dir / "p5_group_fill_heatmap.png", dpi=150, bbox_inches="tight")
    plt.close(fig)

    # Plot 6 — selected vs all eligible candidates
    el = cand[cand.eligible]
    fig, axes = plt.subplots(1, 2, figsize=(13, 4.5))
    axes[0].hist(el.osm_m / 1000, bins=30, alpha=0.5, density=True, label=f"eligible ({len(el)})")
    axes[0].hist(sel.osm_m / 1000, bins=15, alpha=0.6, density=True, label=f"selected ({len(sel)})")
    axes[0].set_xlabel("OSM route length (km)")
    axes[0].set_title("Plot 6a — Route length")
    axes[0].legend()
    axes[1].hist(el.arterial_share, bins=20, alpha=0.5, density=True, label="eligible")
    axes[1].hist(sel.arterial_share, bins=10, alpha=0.6, density=True, label="selected")
    for x in (C.V2_SUBARTERIAL_MAX_SHARE, C.V2_ARTERIAL_MIN_SHARE):
        axes[1].axvline(x, color="k", ls=":")
    axes[1].set_xlabel("share of length on motorway/trunk/primary")
    axes[1].set_title("Plot 6b — Arterial share")
    axes[1].legend()
    fig.savefig(fig_dir / "p6_selected_vs_candidates.png", dpi=150, bbox_inches="tight")
    plt.close(fig)

    # Plot 7 — landmark usage and zone coverage
    use = pd.concat([sel.origin_id, sel.dest_id]).value_counts().reindex(lm.landmark_id, fill_value=0)
    zones = pd.concat([sel.origin_zone, sel.dest_zone]).value_counts()
    fig, axes = plt.subplots(1, 2, figsize=(15, 4.5), gridspec_kw={"width_ratios": [3, 1]})
    axes[0].bar(use.index, use.values, color="#577590")
    axes[0].tick_params(axis="x", rotation=90, labelsize=7)
    axes[0].set_title(f"Plot 7a — Routes per landmark (cap {C.V2_MAX_LANDMARK_USES}; "
                      f"unused: {(use == 0).sum()})")
    axes[1].bar(zones.index, zones.values, color="#90be6d")
    axes[1].set_title("Plot 7b — Route endpoints per zone")
    fig.savefig(fig_dir / "p7_landmark_usage_zones.png", dpi=150, bbox_inches="tight")
    plt.close(fig)

    # Plot 8 — OSM length vs straight line (detour factor for the naive baseline)
    fig, ax = plt.subplots(figsize=(7, 6))
    ax.scatter(el.straight_m / 1000, el.osm_m / 1000, s=6, alpha=0.3, label="eligible")
    ax.scatter(sel.straight_m / 1000, sel.osm_m / 1000, s=18, color="red", label="selected")
    med = float(np.median(el.osm_m / el.straight_m))
    xx = np.linspace(0, el.straight_m.max() / 1000, 10)
    ax.plot(xx, xx, "k:", label="1.0×")
    ax.plot(xx, med * xx, "k--", label=f"median detour {med:.2f}×")
    ax.set_xlabel("Straight-line distance (km)")
    ax.set_ylabel("OSM shortest-path length (km)")
    ax.set_title("Plot 8 — Detour factor")
    ax.legend()
    fig.savefig(fig_dir / "p8_detour_factor.png", dpi=150, bbox_inches="tight")
    plt.close(fig)


# =====================================================================
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("legs", help="offline: hotspot leg geometries")
    g = sub.add_parser("geocode", help="PAID: landmark names -> coordinates")
    g.add_argument("--dry-run", action="store_true", help="count calls and cost, no network")
    g.add_argument("--only", help="comma-separated landmark_ids to (re)query")
    g.add_argument("--provider", choices=["places", "geocoding"], default="places")
    g.add_argument("--evaluate-only", action="store_true", help="re-run checks on cached responses (no network)")
    p = sub.add_parser("pairs", help="offline: routes, tags, selection, plots")
    p.add_argument("--source", choices=["approx", "geocoded"], default="geocoded")
    args = ap.parse_args()

    if args.cmd == "legs":
        cmd_legs(args)
    elif args.cmd == "geocode":
        if args.evaluate_only:
            evaluate_geocodes(pd.read_csv(C.V2_LANDMARKS_SEED_CSV), args.provider)
        else:
            cmd_geocode(args)
    else:
        cmd_pairs(args)


if __name__ == "__main__":
    main()
