# Stage 6 v2 — LLM vs Google Maps routing benchmark

Branch: `benchmark-v2` · v1 snapshot: commit `0df60ba` on `main` · outputs: `data/benchmark_v2/`

## Read in this order
| Doc | What it holds (single source of truth for…) |
|---|---|
| [AUDIT_v1.md](AUDIT_v1.md) | Why v1 was redone — Phase 0 findings with numbers |
| [METHODOLOGY.md](METHODOLOGY.md) | Definitions, formulas, thresholds (landmark, route, query, tags, hotspot, metrics) |
| [DECISIONS.md](DECISIONS.md) | Dated decision log — what, why, alternatives, who approved |
| [DATA_DICTIONARY.md](DATA_DICTIONARY.md) | Every v2 file and column |
| [BILLING_AND_KEYS.md](BILLING_AND_KEYS.md) | API keys, billing, quotas, error → fix table |
| [RUN_LOG.md](RUN_LOG.md) | Every script run: date, command, API calls, outputs, observations |

## Pipeline (v2)
```
[0] baseline commit + branch                                   DONE
[1] ROUTES  landmarks_seed.csv ─🛑─► geocode (paid, ask) ─🛑─► pairs (offline) ─🛑 professor
[2] GOOGLE  predicted traffic, 28 queries/route, polyline → OSM road list → final tags
[3] LLM     grounding check → condition A (thinking off) + consistency subset
[3b] LLM    condition B (thinking on) — last, costliest, ask first
[4] METRICS log-ratio, abs error, time-of-day sensitivity, traffic awareness,
            road validity, Jaccard overlap, repeat spread, naive baseline — by stratum
[5] CHARTS + narrative vs midsem hypotheses
[later] C context ablation · OSM-Dijkstra ground truth · other LLMs · MapmyIndia
```

## Current status
| Step | Status |
|---|---|
| 0 Baseline + branch | ✅ done (2026-09-30) |
| 0b Docs | ✅ done |
| 1a Landmark seed list | ✅ 70 landmarks drafted — **awaiting Ishan's review (Gate 1)** |
| 1a Geocode | ⏳ script ready, dry-run done (70 calls, ≈ $0) — **needs approval to run** |
| 1b Pairs / tags / selection | ✅ script works; rehearsed offline on approximate coords (72 routes, all 18 groups filled) — real run after geocoding |
| 2–5 | not started |

## Scripts (in `src/llm_benchmark/`)
| Script | Purpose | API calls? |
|---|---|---|
| `1b_build_od_pairs.py legs` | Hotspot-leg geometries from raw Stage-2 JSON | No |
| `1b_build_od_pairs.py geocode [--dry-run]` | Landmark names → coordinates + checks | **Yes** (Places), cached |
| `1b_build_od_pairs.py pairs [--source approx\|geocoded]` | OSM routes, tags, balanced selection, plots | No |
| v1 scripts `1_…` – `6_…`, `test_pipeline.py` | Kept unchanged for the pilot section | — |
