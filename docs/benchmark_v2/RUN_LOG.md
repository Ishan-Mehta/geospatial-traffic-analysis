# Run log (v2)

One entry per script run that produces or changes data. Newest last.
Format: date · command · API calls (paid?) · outputs · observations.

| # | Date | Command | API calls | Outputs | Observations |
|---|---|---|---|---|---|
| R-01 | 2026-09-30 | Phase 0 audit (ad-hoc read-only analysis) | 0 | [AUDIT_v1.md](AUDIT_v1.md) | See audit |
| R-02 | 2026-09-30 | `git commit` baseline `0df60ba` on `main`; `git checkout -b benchmark-v2` | 0 | — | `data/raw/gmaps_data/` (1.6 GB) and `src/analysis/cache/` added to `.gitignore` |
| R-03 | 2026-09-30 | `1b_build_od_pairs.py legs` | 0 | `hotspot_legs.geojson`, `figures/phase1/p3_hotspot_legs_map.png` | 689 legs → 564 plausible → 113 hotspots (CV ≥ 0.279). All 564 geometries found in the first raw file (`…20260401_215216.json`) |
| R-04 | 2026-09-30 | `1b_build_od_pairs.py pairs --source approx` (rehearsal, 1st) | 0 | `rehearsal_approx/` | 2,318 candidates; 98.5 % "crossed" a hotspot under the 300 m rule → 5 groups empty (→ D-17). Trinity Circle unroutable (35 pairs) (→ D-18). Plot bug (itertuples + underscore columns) fixed |
| R-05 | 2026-09-30 | `1b_build_od_pairs.py pairs --source approx` (rehearsal, after fixes; run twice) | 0 | `rehearsal_approx/od_pairs.csv` + 7 figures | 2,252 eligible (52 outside bands, 14 short non-compact). **72 selected, all 18 groups = 4.** Identical md5 on rerun (deterministic). Shortest selected route 2.3 km (no < 2 km routes selected). Rehearsal only — approximate coordinates, not benchmark data |
| R-06 | 2026-09-30 | `1b_build_od_pairs.py geocode --dry-run` | 0 | — | 70 landmarks → 70 Places calls needed; ≤ $2.24 list price, expected $0 (free cap 5,000/month) |
| R-07 | 2026-10-01 | Free Places test call (field mask `places.id` only, $0 SKU) | 1 (free) | — | HTTP 200 → Places API (New) is enabled on the Maps key |
| R-08 | 2026-10-01 | `1b_build_od_pairs.py geocode` (approved by Ishan) | **70 Places Text Search (Pro SKU)**, within free cap → $0 expected | `cache/places/*.json`, `landmarks_geocoded.csv`, `landmarks_review.csv` | All 70 returned results. 46 OK, 24 FLAG. Plot step crashed (`df.flags` is a pandas attribute) → fixed, re-evaluated from cache with `--evaluate-only` (0 calls). Rough coordinates vs Google: median 82 m, max 1.25 km among OK rows |
| R-09 | 2026-10-01 | `geocode --only L07,L19` (approved: Lalbagh Metro replacement, IISc gate retry) | **2 Places calls** (≈ $0) | cache, `landmarks_geocoded.csv` | L07 Lalbagh Metro Station: OK (name 100, 2 m from road). L19 IISc retry: campus centroid again (282 m) → dropped (D-24). `review_decisions.csv` wired into the checks |
| R-10 | 2026-10-01 | `geocode --evaluate-only` | 0 | `landmarks_geocoded.csv`, `landmarks_review.csv`, p1, p2 | 47 OK · 19 APPROVED · 4 DROPPED · 0 unresolved → 66 usable |
| R-11 | 2026-10-01 | `pairs --source geocoded` | 0 | `candidate_pairs.csv`, `od_pairs.csv` (md5 cbb2e135…), `od_pairs.geojson`, figures p1, p4–p8 | 2,059 candidates → 2,019 eligible (30 outside bands, 10 short non-compact). Band medians of hotspot share 0.506 / 0.533 / 0.604. **72 routes, 18 groups × 4.** 64/66 landmarks used; 1 route < 2 km; median detour 1.22 |
| R-12 | 2026-10-01 | Wrote `PHASE1_RESULTS.md` (summary + full route table) | 0 | docs | For Gate 3 |
| R-13 | 2026-10-01 | Refactor: helpers → `v2_common.py`; `1b… pairs --source geocoded` rerun | 0 | `od_pairs.csv` | md5 unchanged `cbb2e135…` (refactor is behaviour-neutral) |
| R-14 | 2026-10-01 | `4_query_gmaps_v2.py --dry-run` | 0 | — | 2,016 queries; reference week would be Mon 2026-10-05 if run now; list price $20.16, expected $0 |
| R-15 | 2026-10-01 | `4_query_gmaps_v2.py --mock --limit 5`, then `--mock` | 0 (mock) | `mock/gmaps/` | Resume verified (5 + 2,011) |
| R-16 | 2026-10-01 | `4b_process_gmaps_v2.py --mock` (twice) | 0 | `mock/gmaps/*.csv`, `mock/figures/phase2/` | 1st: 18 % endpoint offsets > 150 m, all large sites → tolerance rule D-29; 2nd: 100 % within tolerance |
| R-17 | 2026-10-01 | `3_query_llm_v2.py select-consistency` | 0 | `consistency_routes.csv` | 1st pick lopsided → balanced greedy (D-31): bands 4/3/3, types 4/3/3, exposure 5/5 |
| R-18 | 2026-10-01 | `3_query_llm_v2.py` dry-runs (grounding, A --part all, B) | 0 | — | 64 calls ≈ $0.22 · 2,576 ≈ $9 · 2,016 ≈ $46 |
| R-19 | 2026-10-01 | Mock LLM runs (grounding, A all, B limit 10), fake-SDK and fake-HTTP error tests, fatal-stop test | 0 | `mock/llm/` | All error kinds classified correctly; resume and fatal stop verified; mock RNG bug (ms-clock seed) fixed |
| R-20 | 2026-10-01 | Applied D-26/27/28/35/36/37; dry-runs + full mock rerun (Google 2,016 + 4b + LLM sample) | 0 | `mock/` | Estimates with gemini-3.8-flash: grounding ≈ $0.09 · A + consistency ≈ $3.81 · B ≈ $19.2. Mock path-mode tags work (`modal_path_share`). Karnataka 2026 holiday check: Mahalaya Amavasya 10 Oct, Dasara 11–21 Oct (holidays 20–21) → reference week must be chosen (D-37) |
| R-21 | 2026-10-01 | Applied D-37…D-41 (pinned week + calendar notes, clock time in prompt, schema descriptions); dry-runs + mock checks | 0 | `mock/` | Dry-run shows deadline Mon 05 Oct 07:30 IST and the calendar notes; SDK accepts the schema with descriptions; Saturday/Sunday queries tagged in `gmaps_queries.csv` |
| R-22 | 2026-10-01 | Sunday tag removed; gemini-2.5-flash added; grounding rule implemented; mock grounding + dry-runs; git untracked Google/LLM data (D-43) | 0 | — | gemini-2.5-flash A dry-run: 2,016 calls ≈ $1.90; SDK accepts `thinking_budget` 0 / −1; locality matching sanity-checked on 4 examples; files remain on disk, now git-ignored |
| R-23 | 2026-10-01 | Added `--workers`; mock A+consistency with 4 workers, rerun, fatal-stop test with 4 workers | 0 | `mock/llm/` | 2,576 unique OK, 0 duplicates, ~7 s; rerun 0 calls; fatal stop after 4 in-flight calls (36 not sent) |
