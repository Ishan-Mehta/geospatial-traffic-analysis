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
