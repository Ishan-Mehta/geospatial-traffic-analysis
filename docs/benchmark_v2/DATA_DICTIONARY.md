# Data dictionary (v2)

All paths relative to `data/benchmark_v2/`. Producer = script in `src/llm_benchmark/`.
Definitions of tags/thresholds: [METHODOLOGY.md](METHODOLOGY.md).

## landmarks_seed.csv — hand-written input (Claude drafts, Ishan reviews)
| Column | Meaning |
|---|---|
| `landmark_id` | L01…; stable id |
| `llm_name` | Exact string the LLM receives as Origin/Destination |
| `search_query` | String sent to Places Text Search (may be more specific than `llm_name`) |
| `kind` | metro_station, junction (compact) · bus_station, rail_station, hospital, tech_park, mall, campus, landmark |
| `expected_area` | Locality expected in Google's formatted address (check `area_ok`) |
| `zone` | Central / North / East / South / West (coverage plots only) |
| `approx_lat`, `approx_lng` | Claude's approximate coordinate — **check + rehearsal only, never sent to APIs or used in results** (D-15) |
| `notes` | Known risks (large site, flyover, uncertain approx, rename) |

## landmarks_geocoded.csv / landmarks_review.csv — `1b_build_od_pairs.py geocode`
Seed columns plus:
| Column | Meaning |
|---|---|
| `lat`, `lng`, `place_id` | Top Places result — **the coordinate Google Routes will receive** |
| `returned_name`, `formatted_address`, `primary_type`, `n_results` | From Places |
| `name_score` | token-set similarity llm_name ↔ returned_name (0–100) |
| `area_in_address` | `expected_area` found in address |
| `approx_dist_m` | result ↔ approximate coordinate |
| `ambiguity_m` | distance to the farthest other good name match (0 = none) |
| `snap_m` | distance to nearest drivable OSM edge |
| `status` | OK · FLAG · NOT_QUERIED · APPROVED (set manually after review) |
| `flags` | Reasons for FLAG |
`landmarks_review.csv` = rows with status ≠ OK.

## hotspot_legs.geojson — `1b_build_od_pairs.py legs`
One LineString per plausible Stage-4 leg (564). Columns: `sub_route_id`, `road_name` (BBMP road the leg belongs to), `distance_meters`, `straight_m`, `detour`, `snapshot_count`, `mean_live_s`, `std_live_s`, `cv_live` (= std/mean), `is_hotspot` (top 20 % CV).

## candidate_pairs.csv / od_pairs.csv — `1b_build_od_pairs.py pairs`
`od_pairs.csv` = selected subset of `candidate_pairs.csv`, plus `route_id` (R001…).
| Column | Meaning |
|---|---|
| `origin_*`, `dest_*` | id, name (LLM string), lat, lng (Google input), place_id, kind, zone |
| `straight_m` | great-circle distance between endpoints |
| `osm_m`, `detour` | provisional OSM shortest-path length; osm_m / straight_m |
| `band` | B1_1-5km · B2_5-12km · B3_12-25km |
| `arterial_share`, `road_type` | share on motorway/trunk/primary(+links); arterial / mixed / sub_arterial |
| `hotspot_overlap_m`, `hotspot_share`, `hotspot_band_median`, `hotspot_exposure` | overlap with buffered hotspot legs; share of route; band median; high / low |
| `group` | `band|road_type|{high,low}_hotspot` |
| `osm_road_names` | ordered OSM `name` tags along the provisional path (" \| " separated) |
| `eligible`, `ineligible_reason` | outside_bands · short_non_compact · no_osm_path |
| `coord_source` | approx (rehearsal) or geocoded |
Tags here are **provisional** (OSM path); Phase 2 recomputes them from Google's polyline.

## od_pairs.geojson
Selected routes as LineStrings (provisional OSM paths) with all `od_pairs.csv` columns — open in QGIS.

## figures/phase1/
| File | Content |
|---|---|
| p1_landmarks_map.png | landmarks by kind, flagged circled |
| p2_geocode_quality.png | pass/flag per check; snap-distance histogram |
| p3_hotspot_legs_map.png | plausible legs, hotspots in red |
| p4_selected_routes_map.png | selected routes by band; dashed = high hotspot exposure |
| p5_group_fill_heatmap.png | selected (and eligible) per group |
| p6_selected_vs_candidates.png | length and arterial-share distributions |
| p7_landmark_usage_zones.png | routes per landmark; endpoints per zone |
| p8_detour_factor.png | OSM length vs straight line; median detour (naive baseline input) |

## rehearsal_approx/
Same outputs as above, computed from **approximate** coordinates to test the pipeline before paying for geocoding. Not benchmark data; kept for transparency.

## cache/places/, cache/geocoding/
Raw API responses keyed by a hash of the query (reruns are free). Safe to keep; do not edit.
