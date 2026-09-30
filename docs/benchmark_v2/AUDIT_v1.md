# Audit of the v1 benchmark (Phase 0, 2026-09-30)

Read-only audit of `src/llm_benchmark/` v1 (commit `0df60ba`) and its data. No API calls were made.
v1 stays in the repo unchanged; these findings feed the "pilot / lessons learned" section of the report.

## 1. Suspected problems — verdicts
| # | Suspicion | Verdict | Evidence |
|---|---|---|---|
| 1 | Routes are Stage-4 sensor legs, not trips | **Confirmed** | 10/14 routes < 1.5 km, 6 < 500 m, one is 35 m (`leg_9c2f11c7…`) |
| 2 | Reverse-geocoded names don't describe the leg | **Confirmed** | "Start of X"/"End of X" (same place) on 3 routes; destination literally `4) (Kengeri)` (split of "SH-17-NH-4"); "Bengaluru → Ashok Nagar" for a 162 m leg. LLM read "Vishveshwaraya Nagar" as east Bangalore (route via Old Madras Rd/Halasuru); the coordinate is in the west (lng 77.477) |
| 3 | Routes 1 & 3 come from mis-geocoded waypoints | **Confirmed** | S-27 (BBMP length 7 km): chain NH-7 → 12.9956,77.6651 (east, wrong) → "Vishweshwaraiahnagara" 12.9686,77.4774 (wrong namesake, west) ⇒ 30.3 km leg. S-04 (4 km): "Jyothinagara" → 12.9569,77.5200 (Chandra Layout, wrong) ⇒ 27.1 km leg; its "ITI Colony Gate" → 13.1400,77.3502 (outside city, also the endpoint of a dropped long_distance leg) |
| 4 | Category ranking favours noisy / zero-telemetry legs | **Confirmed, different mechanism** | low_congestion picks are *not* zero-variance: live < static consistently (e.g. live 14–29 s vs static 37 s). **588/689 legs have negative mean congestion ratio** → Google's leg-level `staticDuration` is inflated; "bottom congestion" = most anomalous. high_delay uses raw seconds → favours long legs (top two: 158 km, 369 km) |
| 5 | `route_match_score` meaningless; no polyline | **Confirmed** | difflib ratio vs Google's short `description`; `GMAPS_FIELD_MASK` lacks `routes.polyline` |
| 6 | Single sample, no temperature/seed, thinking off | **Confirmed** | No temperature/seed in `GenerateContentConfig`; `thinking_budget=0`; model version not logged |

## 2. Category arithmetic
25 configured → 20 after de-dup (one long_distance route was also high_delay) → 14. The 6 dropped = 4 long_distance + **2 high_delay** (158 km, 369 km; Shivamogga / Hiriyur direction). The drop was manual — no script does it (not reproducible).

## 3. Additional bugs found
1. **Only 1 of 22 LLM records succeeded.** 21 have `raw_response: null`. `3_query_llm.py` appends failed attempts and resume treats them as done (never retried). Error text isn't saved; ~10 s spacing matches the "genuine error" branch (3 tries × 5 s), not the 429 branch — so "20 req/day" may not be the actual cause.
2. `5_compare_results.py`: failed LLM record → distance/time default 0 → fake −100 % error; means not medians; "latest file by mtime" may pick the wrong model's file.
3. `4_query_gmaps.py`: results written only at the end (crash = total loss), no resume, negative delay clipped to 0.
4. `test_pipeline.py`: tests row 0 of `benchmark_routes.csv` = the dropped 158 km leg; different prompt, thinking on, no departure time.
5. `2_reverse_geocode.py` cannot produce the names in `benchmark_routes_geocoded.csv` → that file was hand-edited.
6. Stage-4 legs have 44 snapshots (max 88), not 84 as reported — leg IDs likely changed mid-week. 32/689 legs lie outside Bangalore, 251 are > 10 km.
7. `src/llm_benchmark/` and `data/benchmark/` were untracked in git (fixed by the baseline commit).
8. `PROJECT_CONTEXT.md` says 22/112 LLM queries done; the true count is 1.

## 4. Stage-4 leg plausibility (used for hotspot tagging in v2)
| Filter | Legs remaining |
|---|---|
| all | 689 |
| inside Bangalore bbox (lat 12.8–13.25, lng 77.4–77.85) | 657 |
| + distance ≤ 2 × straight line | 571 |
| + ≥ 40 snapshots | **564** |

## 5. Settings recorded
Model `gemini-3.5-flash`, `thinking_budget=0`, temperature = SDK default (unset), no seed. GMaps field mask: `routes.duration,routes.staticDuration,routes.distanceMeters,routes.description,routes.travelAdvisory.speedReadingIntervals` (no polyline).
