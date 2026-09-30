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
