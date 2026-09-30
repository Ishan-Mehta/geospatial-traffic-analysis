# Methodology (v2) — definitions, formulas, thresholds

All numeric thresholds live in `src/llm_benchmark/config.py` (section `V2`); this doc explains them.
Decisions and their reasons are in [DECISIONS.md](DECISIONS.md).

## 1. Units of the benchmark
| Term | Definition |
|---|---|
| **Landmark** | A named, precise place (metro station, junction, hospital, tech park, bus/rail station, mall, campus). Has one `llm_name` (sent to the LLM) and one coordinate (sent to Google), obtained by geocoding that name. |
| **Compact landmark** | `kind` ∈ {metro_station, junction}. Footprint ≲ 100 m. Only compact landmarks may form routes shorter than 2 km. |
| **Route** | Ordered pair origin landmark → destination landmark (`route_id`). No via points. |
| **Query** | One route × one time slot × one day. 4 slots × 7 days = **28 queries per route**. |
| **Time slots** | AM_PEAK 08:00 "Morning Rush", MID_DAY 14:00 "Off-Peak", PM_PEAK 18:00 "Evening Rush", NIGHT 23:00 "Night" (IST). |
| **Days** | Monday … Sunday (the LLM prompt names the weekday; Google gets the next future date of that weekday). |
| **Condition A / B** | Zero-context prompt; A = thinking off, B = thinking on. (C = context ablation, later.) |
| **Sample** | One LLM answer. Condition A: 1 sample per query, plus 2 extra on a 10-route consistency subset. |

## 2. Landmark geocoding (forward: name → coordinate)
1. Places Text Search (New) with `textQuery = search_query`, `locationRestriction` = Bangalore rectangle (`V2_BBOX`), up to 5 results. Fallback: Geocoding API with `bounds` + `components=country:IN`.
2. The top result is chosen. Checks (any failure → `status=FLAG`, never silent drop):

| Check | Rule | Why |
|---|---|---|
| `name_score` | token-set similarity(llm_name, returned name) ≥ 80 | Right place, not a nearby business |
| `area_ok` | `expected_area` appears in the formatted address **or** result within 2 km of my approximate coordinate | Catches wrong namesakes (v1's Vishveshwaraya Nagar) |
| `approx_dist_m` | distance result ↔ approximate coordinate (informational; > 2 km flags) | Independent sanity check |
| `ambiguous` | another result with name_score ≥ 80 lies > 1 km away | Same name exists in several places |
| `type_ok` | primary type is not an area type (locality, sublocality, political, neighborhood, postal_code, administrative_area_*) | Must be a point, not a whole area |
| `snap_m` | distance to nearest OSM drivable edge ≤ 150 m | Google & OSM can route from it |

## 3. Candidate routes and tags (Phase 1b, offline)
- **Candidate pairs**: all landmark pairs with straight-line distance 0.7–22 km. One direction per pair, chosen deterministically (hash of ids) so directions are mixed.
- **Provisional route**: OSM shortest path by length on `output/bangalore_drive.graphml` (drive network, directed, one-ways respected). Endpoints snapped to the nearest node of the graph's largest strongly connected component (155,218 of 155,563 nodes), so every snapped point can reach every other (D-18).
- **Tags** (provisional now; recomputed from Google's polyline in Phase 2 → *final* tags):

| Tag | Definition |
|---|---|
| `band` | route length L: **B1** 1–5 km, **B2** 5–12 km, **B3** 12–25 km (outside → not eligible) |
| `arterial_share` | fraction of L on OSM `highway` ∈ {motorway, trunk, primary} (+ `_link`) |
| `road_type` | arterial if share ≥ 0.60, sub-arterial if ≤ 0.40, else mixed |
| `hotspot_overlap_m` | length of route within 30 m of any hotspot leg (UTM 43N, EPSG:32643) |
| `hotspot_share` | `hotspot_overlap_m` / route length |
| `hotspot_exposure` | **high** if `hotspot_share` ≥ median share of eligible candidates in the same band, else **low** (relative split; see D-17) |

- **Hotspot legs**: Stage-4 legs that pass plausibility (inside bbox, distance ≤ 2× straight line, ≥ 40 snapshots — 564/689) and are in the **top 20 % by coefficient of variation of live duration** (std/mean over snapshots). Congestion ratio is *not* used (588/689 legs negative; see AUDIT_v1 §1.4). Geometry = the leg's Google polyline from the first raw snapshot in which it appears. Result: 113 hotspot legs (CV ≥ 0.279) whose union covers ≈ 603 km of corridors — most arterials — hence the relative exposure tag.

## 4. Selection
- 18 groups = 3 bands × 3 road types × 2 hotspot exposure (high/low). Round-robin over groups, picking the next candidate that satisfies:
  landmark used < `V2_MAX_LANDMARK_USES` (3); not a near-duplicate (both endpoints within 1.5 km of an already selected route's endpoints, either direction); < 2 km ⇒ both endpoints compact.
- Candidates within a group are ordered by a fixed hash → deterministic, no hidden preference.
- Stop at `V2_TARGET_ROUTES` (72) or when no group can add. Unfilled groups are reported.

## 5. Phase 2 — Google ground truth
- **Query**: Google Routes `computeRoutes`, origin/destination = landmark Google coordinates, no via points,
  `TRAFFIC_AWARE_OPTIMAL` + `trafficModel BEST_GUESS`, future `departureTime` = slot time on that weekday of one fixed
  **reference week** (next week's Monday at first run; stored in `gmaps/run_manifest.json`). Semantics: **predicted typical
  traffic**, not live. Up to 3 routes returned; the **primary route = routes[0]** is the ground truth; alternatives are stored.
- **Congestion ratio** = duration / staticDuration of the primary route (≥ 1 means slower than free-flow).
- **Endpoint check**: distance between Google's leg start/end and our coordinate ≤ max(150 m, landmark `snap_m` + 100 m) (D-29).
- **Map-matching**: sample every 20 m along Google's polyline, nearest OSM edge within 25 m; ordered unique `name` tags =
  **ground-truth road sequence**; arterial share = share of matched samples on motorway/trunk/primary(+links);
  `unmatched_frac` reported as a quality measure. Google's step instructions give a second, independent road list.
- **Final tags** (used in all analysis): band, road type and hotspot exposure recomputed from the primary route of the
  reference query (Wednesday MID_DAY, D-28), using the same thresholds and the Phase-1 per-band hotspot medians.
- **Path stability**: number of distinct Google polylines across a route's 28 queries.
- **Peak/night ratio** (Google): mean duration of AM_PEAK+PM_PEAK ÷ NIGHT duration, weekdays and weekends separately.

## 6. Phase 3 — LLM queries
- **Benchmark prompt**: v1 wording and schema (D-13); origin/destination = `llm_name`; weekday name; slot label.
- **Conditions**: A = lowest thinking the model allows (Gemini 3.x: `thinking_level=MINIMAL`; thinking cannot be fully
  disabled), B = `HIGH`; temperature 1.0 explicit; thought tokens logged per answer (D-26).
- **Samples**: 1 per query; consistency subset = 10 routes (`consistency_routes.csv`, balanced greedy pick) × 2 extra
  condition-A samples (sample_idx 1, 2).
- **Grounding check**: separate prompt "Where exactly is <landmark>?" → lat/lng; **misplaced** if > 2 km from the Google
  coordinate; routes with a misplaced endpoint are *flagged* (reported separately), not removed (D-34).
- **valid_numbers**: estimated distance and time both numeric and > 0.

## 7. Planned metrics (Phase 4, detail filled in then)
Log-ratio ln(llm/google) for distance and time; absolute error; over/under direction; medians. Time-of-day sensitivity (LLM peak/night ratio vs Google's). Traffic awareness (Spearman: LLM label vs Google congestion ratio). Road validity (LLM road names fuzzy-matching OSM names). Road overlap (Jaccard LLM roads vs the map-matched Google road sequence). Repeat spread (consistency subset). Naive baseline: straight line × 1.22 detour at a per-slot typical speed. All broken down by band, road type, hotspot exposure (final tags), slot, day; grounding-flagged routes reported separately.
