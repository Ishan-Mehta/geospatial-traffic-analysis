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
| `rough_lat`, `rough_lng` | Claude's approximate coordinate — **check + rehearsal only, never sent to APIs or used in results** (D-15) |
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
| `status` | OK (all checks pass) · FLAG (needs review) · APPROVED (flagged, approved in `review_decisions.csv`) · DROPPED (excluded by review) · NOT_QUERIED |
| `flags` | Reasons for FLAG (kept after approval, for the record) |
| `review_decision`, `review_reason` | Copied from `review_decisions.csv` |
`landmarks_review.csv` = rows with status ≠ OK.

## review_decisions.csv — Gate-2 human decisions (read by `geocode`)
`landmark_id`, `decision` (APPROVE / DROP), `reason`, `approved_by`, `date`. Only landmarks with a decision appear.

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

## consistency_routes.csv — `3_query_llm_v2.py select-consistency`
The 10 routes that get 2 extra condition-A samples: `route_id`, names, `band`, `road_type`, `hotspot_exposure`, `group`.

## gmaps/ — Phase 2 (`4_query_gmaps_v2.py`, `4b_process_gmaps_v2.py`)
| File | Content |
|---|---|
| `run_manifest.json` | reference Monday, routing preference, traffic model, alternatives flag, field mask, days, slots, `od_pairs.csv` md5, "predicted" semantics |
| `gmaps_responses.jsonl` | one line per query attempt: `route_id, day, slot_id, slot_time, departure_ist, departure_utc, status (ok/error), error, http_status, routes[] {distance_m, duration_s, static_duration_s, description, route_labels, polyline [lng,lat], start_location, end_location, steps[] {distance_m, instruction, maneuver}}, n_routes, request (no key), query_timestamp, latency_s, mock, traffic_semantics` |
| `gmaps_queries.csv` | one row per OK query: distance/duration/static, `congestion_ratio`, `n_routes`, `alt_distances_m`, `start/end_offset_m`, `start/end_allowed_m`, `endpoints_ok`, `path_key` (hash of polyline), `osm_road_seq`, `n_osm_roads`, `arterial_share_google`, `unmatched_frac`, `hotspot_overlap_m_google`, `hotspot_share_google`, `google_step_roads` |
| `gmaps_routes.csv` | one row per route: `reference_query`, Google vs provisional distance / band / arterial share / road type / hotspot exposure / group, `group_changed`, `n_distinct_paths`, duration min/median/max, `peak_night_ratio_weekday/weekend`, `endpoints_ok_all`, `max_endpoint_offset_m`, `median_unmatched_frac` |
| `../figures/phase2/q1…q7` | Google vs OSM length · congestion heatmap slot×day · duration by slot per band · tag changes · endpoint offsets · path stability · peak/night ratio |

## llm/ — Phase 3 (`3_query_llm_v2.py`)
| File | Content |
|---|---|
| `<model>_grounding.jsonl` | per landmark: `landmark_id, llm_name, prompt`, answer `{locality, latitude, longitude, confidence}`, run metadata (below) |
| `<model>_grounding_results.csv` | Google vs LLM point, `error_m`, `misplaced` (> 2 km) |
| `<model>_grounding_route_flags.csv` | per route: `origin_misplaced`, `dest_misplaced`, `grounding_flag` |
| `<model>_A.jsonl`, `<model>_B.jsonl` | per query × sample: `route_id, day, slot_id, slot_label, sample_idx, origin/dest id+name, prompt`, `parsed_response {suggested_route, estimated_distance_km, estimated_time_minutes, traffic_awareness, reasoning}`, `raw_response`, `valid_numbers` + metadata |
Run metadata on every LLM record: `kind, condition, model_key, provider, model_name, model_version, settings {temperature, thinking_level}, system_prompt_sha1, status, attempts, prompt_tokens, output_tokens, thought_tokens, latency_s, error, error_kind, mock, query_timestamp`.

## mock/ — git-ignored
Same structure as `gmaps/`, `llm/`, `figures/` but produced with `--mock` (fake answers). Pipeline tests only, never results.

## cache/places/, cache/geocoding/
Raw API responses keyed by a hash of the query (reruns are free). Safe to keep; do not edit.
