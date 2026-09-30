# Stage 6 v2 — LLM vs Google Maps routing benchmark

Branch: `benchmark-v2` · v1 snapshot: commit `0df60ba` on `main` · outputs: `data/benchmark_v2/`

## Read in this order
| Doc | What it holds (single source of truth for…) |
|---|---|
| [PHASE1_RESULTS.md](PHASE1_RESULTS.md) | **The 72-route list + Phase 1 summary** (for Ishan / professor) |
| [AUDIT_v1.md](AUDIT_v1.md) | Why v1 was redone — Phase 0 findings with numbers |
| [METHODOLOGY.md](METHODOLOGY.md) | Definitions, formulas, thresholds (landmark, route, query, tags, hotspot, metrics) |
| [DECISIONS.md](DECISIONS.md) | Dated decision log — what, why, alternatives, who approved |
| [DATA_DICTIONARY.md](DATA_DICTIONARY.md) | Every v2 file and column |
| [BILLING_AND_KEYS.md](BILLING_AND_KEYS.md) | API keys, billing, quotas, error → fix table |
| [RUN_LOG.md](RUN_LOG.md) | Every script run: date, command, API calls, outputs, observations |

## Current status (2026-10-01)
| Step | Status |
|---|---|
| 0 Baseline commit + branch | ✅ done |
| 0b Docs | ✅ done (kept up to date) |
| 1a Landmarks: seed → geocode → review | ✅ 70 drafted → 72 Places calls (≈ $0) → **66 usable** (47 OK + 19 approved; 4 dropped, 1 replaced) |
| 1b Routes: candidates → tags → selection | ✅ **72 routes, 4 in each of 18 groups** |
| **Gate 3** — Ishan + professor review the route list | ⏳ **waiting** ([PHASE1_RESULTS.md](PHASE1_RESULTS.md)) |
| 2 Google ground truth | not started |
| 3 / 3b LLM queries | not started |
| 4 Metrics · 5 Charts + narrative | not started |

API usage so far: 1 free Places test call + 72 Places Text Search calls (inside the 5,000/month free cap). No Routes or Gemini calls in v2 yet.

## Where everything is
| What | Path |
|---|---|
| Landmark input (hand-written) | `data/benchmark_v2/landmarks_seed.csv` |
| Gate-2 human decisions | `data/benchmark_v2/review_decisions.csv` |
| Geocoded landmarks (Google coordinates + check results) | `data/benchmark_v2/landmarks_geocoded.csv` (non-OK rows also in `landmarks_review.csv`) |
| Raw Places responses (cache, reruns free) | `data/benchmark_v2/cache/places/` |
| Hotspot legs (Stage-4 legs + CV + geometry) | `data/benchmark_v2/hotspot_legs.geojson` |
| All candidate routes with tags | `data/benchmark_v2/candidate_pairs.csv` |
| **Final route list** | **`data/benchmark_v2/od_pairs.csv`** (+ `od_pairs.geojson` for QGIS) |
| Phase-1 plots (8) | `data/benchmark_v2/figures/phase1/` |
| Offline rehearsal (approximate coords, not results) | `data/benchmark_v2/rehearsal_approx/` |
| Config (all thresholds) | `src/llm_benchmark/config.py` → section `V2` |
| Phase-1 script | `src/llm_benchmark/1b_build_od_pairs.py` |
| v1 (pilot) scripts and data, unchanged | `src/llm_benchmark/1_…6_*.py`, `data/benchmark/` |

## Scripts
| Command (run from `src/llm_benchmark/`) | Purpose | API calls? |
|---|---|---|
| `python 1b_build_od_pairs.py legs` | Hotspot-leg geometries from raw Stage-2 JSON | No |
| `python 1b_build_od_pairs.py geocode --dry-run` | Count calls + cost | No |
| `python 1b_build_od_pairs.py geocode [--only L07,L19]` | Landmark names → coordinates + checks | **Yes** (Places, cached) |
| `python 1b_build_od_pairs.py geocode --evaluate-only` | Re-run checks + apply `review_decisions.csv` | No |
| `python 1b_build_od_pairs.py pairs [--source approx\|geocoded]` | OSM routes, tags, balanced selection, plots | No |

## Next steps (in order; 🛑 = Ishan decides / approves)
**🛑 Gate 3 — route list review** (Ishan + professor, using PHASE1_RESULTS.md). Changes → edit seed/decisions, rerun `pairs` (free).

**Phase 2 — Google ground truth** (`4_query_gmaps_v2.py`; v1 `4_query_gmaps.py` untouched)
1. Build the script: reads `od_pairs.csv`; 28 queries per route (Mon–Sun × 08:00/14:00/18:00/23:00 IST) with future `departureTime`s all inside **one fixed reference week** (so every query predicts the same calendar week); `TRAFFIC_AWARE`, no via points.
   Field mask: duration, staticDuration, distanceMeters, encoded polyline, legs start/end location, step navigation instructions (Google's road names), description. No traffic-on-polyline (keeps the cheaper Pro SKU — SKU to be re-verified in Google's docs before running).
   Writes one JSONL line per query as it arrives; resume-safe; failures logged with the error and never counted as done.
2. `--dry-run` → call count (2,016) + cost (expected $0 inside 5,000 free) → **🛑 approval** → 1 test query shown to Ishan → full run.
3. Offline post-processing: decode polylines → snap to OSM → ordered road-name list per query; check Google's start/end point is ≤ 150 m from ours; **final tags** from Google's route; table of routes whose group changed. **🛑 decide** which query's route defines a route's final tags if Google picks different roads at different times (proposal: the MID_DAY Wednesday route, with a sensitivity check).
4. Phase-2 plots: Google vs OSM length; Google travel time by slot × day per band; congestion (duration/staticDuration) heatmap; tag changes.

**Phase 3 — LLM, condition A** (`3_query_llm_v2.py` + `llm_clients.py`, provider-agnostic; v1 untouched)
1. Build the adapter layer + script (fixed error handling, model version, explicit temperature, token counts).
2. Grounding check: ask the LLM where each of the 64 used landmarks is → flag routes whose landmark the LLM misplaces by > 2 km. **🛑 approval** (~64 calls).
3. Condition A (thinking off): 2,016 queries + consistency subset (10 routes × 28 × 2 extra = 560). Billing on the Gemini key is needed (BILLING_AND_KEYS.md A). **🛑 approval** after dry-run + 1 test call. ≈ $8.

**Phase 4 — metrics** (`5_compare_results_v2.py`): log-ratio and absolute error (distance, time), over/under, medians; time-of-day sensitivity (LLM peak/night ratio vs Google's); traffic-awareness Spearman; road validity vs OSM names; Jaccard road overlap; repeat spread; naive baseline (straight line × 1.22 detour at per-slot typical speed); all split by band / road type / hotspot / slot / day; grounding-check failures reported separately.

**Phase 5 — charts + narrative** (`6_visualize_benchmark_v2.py`): log-scale scatters, time-of-day sensitivity plot, validity/overlap bars, error by group; findings vs midsem hypotheses; v1 as "pilot / lessons learned".

**Phase 3b — condition B (thinking on)** — last, costliest (≈ $25–60): **🛑 separate approval**.

**Later (optional):** condition C context ablation · OSM-Dijkstra ground truth (midsem idea) · other LLMs · MapmyIndia.
