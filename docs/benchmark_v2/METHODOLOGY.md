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
  **reference week** (pinned Mon 5 – Sun 11 Oct 2026, D-37; stored in `gmaps/run_manifest.json`; `calendar_note` tags the Sat 10 Oct public holiday; Sun 11 Oct deliberately untagged). Semantics: **predicted typical
  traffic**, not live. Up to 3 routes returned; the **primary route = routes[0]** is the ground truth; alternatives are stored.
- **Traffic index** = duration ÷ the route's fastest duration over its 28 queries (≥ 1; 1 = the route's best case) — the
  traffic measure used in the metrics (D-48). `congestion_ratio` = duration / staticDuration is kept for reference only:
  Google's staticDuration is the ETA from *historical* traffic, not free-flow (ratio < 1 at night).
- **Endpoint check**: distance between Google's leg start/end and our coordinate ≤ max(150 m, landmark `snap_m` + 100 m) (D-29).
- **Map-matching**: sample every 20 m along Google's polyline, nearest OSM edge within 25 m; a name counts only if it holds
  ≥ 3 consecutive samples (~60 m, removes junction flicker, D-47); ordered unique `name` tags = **ground-truth road sequence**; arterial share = share of matched samples on motorway/trunk/primary(+links);
  `unmatched_frac` reported as a quality measure. Google's step instructions give a second, independent road list.
- **Final tags** (used in all analysis): band, road type and hotspot exposure recomputed from the primary route of the
  most frequent Google path (tie → Wednesday MID_DAY, D-28), same thresholds and Phase-1 per-band hotspot medians; Google routes
  of 25–29 km go into the top band (D-48).
- **Path stability**: number of distinct Google polylines across a route's 28 queries.
- **Peak/night ratio** (Google): mean duration of AM_PEAK+PM_PEAK ÷ NIGHT duration, weekdays and weekends separately.

## 6. Phase 3 — LLM queries
- **Benchmark prompt**: v1 wording (D-13) with the clock time appended to the slot label, e.g. "Evening Rush (18:00)" (D-38); schema = v1 fields + one-line descriptions (D-39); origin/destination = `llm_name`; weekday name. Exact text: [IO_SPEC.md](IO_SPEC.md).
- **Conditions**: A = lowest thinking the model allows (gemini-3.8-flash `thinking_level=LOW` — Gemini 3.x cannot fully
  disable thinking; gemini-2.5-flash `thinking_budget=0` = off), B = high (`HIGH` / dynamic `-1`); temperature 1.0 explicit; thought tokens logged per answer (D-26).
- **Samples**: 1 per query; consistency subset = 10 routes (`consistency_routes.csv`, balanced greedy pick) × 2 extra
  condition-A samples (sample_idx 1, 2).
- **Grounding check**: separate prompt "Where exactly is <landmark>?" → locality + lat/lng; **misplaced** if > 2 km from the Google
  coordinate **and** the locality shares no word with Google's address/expected area (rule `coords_and_locality`, D-34); routes with a misplaced endpoint are *flagged* (reported separately), not removed (D-34).
- **valid_numbers**: estimated distance and time both numeric and > 0.

## 7. Phase 4 metrics (implemented in `5_compare_results_v2.py`)
Join key (route, day, slot); one row per query × LLM sample; headline numbers use sample 0 (2,016 rows).
1. **Distance / time accuracy:** ratio = LLM ÷ Google (Google = primary route `distance_m`, `duration_s`); log ratio
   ln(LLM/Google) (symmetric: over- and under-estimation weigh equally); absolute error (km, min); absolute % error;
   over-estimation share. Medians throughout. Time is also compared with Google's staticDuration (reference only).
2. **Uncertainty:** 95 % CI of the median via **route-level cluster bootstrap** (resample routes, 2,000 reps, seed fixed):
   the 28 queries of one route are not independent. Group differences: two-sided **permutation test** on medians of
   per-route values (5,000 permutations).
3. **Time-of-day sensitivity (headline):** per route, weekday peak ÷ night = mean(08:00, 18:00 times) ÷ mean(23:00 time),
   for LLM and Google; compared by log difference and by Spearman across routes. Within-route Spearman between the LLM's
   and Google's 28 times. Profile: each time ÷ the route's weekday-night time, median per slot/day type.
4. **Traffic awareness:** Spearman between the LLM label (none 0 … heavy 3) and Google's traffic index (duration ÷ route's
   fastest of 28, D-48); overall, within each slot, and within route.
5. **Road names** (D-55, D-56): normalisation (lower-case, apostrophes removed, brackets dropped, Rd→Road, ORR→Outer Ring
   Road, NH n→National Highway n, aliases e.g. MG Road = Mahatma Gandhi Road, CMH, OTC, KG Road); reference list of real
   roads = OSM drive-graph names ∪ all road names in Google's step instructions ∪ BBMP road list; fuzzy score = max(token-set
   ratio, space-insensitive character ratio), **match ≥ 85**; generic names ("12th Main Road", "Service Road") count only
   on exact match. **Validity** = share of the LLM's named roads matching the reference (lower bound). **Overlap** with the
   query's Google roads (map-matched OSM names ∪ step names): greedy fuzzy matching → Jaccard, recall (share of Google's
   roads named by the LLM), precision (share of LLM roads on Google's route).
6. **Consistency** (280 queries × 3 samples): coefficient of variation of distance and time; share with identical traffic
   label; mean pairwise Jaccard of road lists; max ÷ min time.
7. **Breakdowns:** final Google tags (band, road type, hotspot exposure), slot, day type, Saturday (holiday) vs Sunday;
   continuous route-level Spearman with arterial share, hotspot share and length; **length-controlled** checks (routes
   ≥ 5 km; within-band correlations) because short routes have larger errors and hold half the sub-arterial routes.
8. **Naive baseline** (D-57): distance = straight line × 1.22 (median OSM detour of Phase-1 candidates, not Google);
   speed = median Stage-2 speed (April scrape, plausible legs ≥ 1 km, snapshots within ±90 min of the slot, weekday /
   weekend); time = distance ÷ speed. Uses exact coordinates (information advantage over the LLM).
9. **Grounding:** routes with a misplaced landmark are flagged (none were).
