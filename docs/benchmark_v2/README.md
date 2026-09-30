# Stage 6 v2 — LLM vs Google Maps routing benchmark

Branch: `benchmark-v2` · v1 snapshot: commit `0df60ba` on `main` · outputs: `data/benchmark_v2/`

## Read in this order
| Doc | What it holds (single source of truth for…) |
|---|---|
| [PHASE1_RESULTS.md](PHASE1_RESULTS.md) | **The 72-route list + Phase 1 summary** (for Ishan / professor) |
| [IO_SPEC.md](IO_SPEC.md) | **Exact prompts, request configs, output formats, and the LLM↔Google comparison row** |
| [CODE_GUIDE_PHASE2_3.md](CODE_GUIDE_PHASE2_3.md) | **How the Phase 2/3 code works, how it was tested, what to decide** (for review) |
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
| 2 Google ground truth | 🧪 code ready + tested offline (mock, fake HTTP, dry-run) — **not run; needs approval** |
| 3 / 3b LLM queries | 🧪 code ready + tested offline (mock, fake SDK, dry-run) — **not run; needs approval + Gemini billing** |
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
| Consistency-subset routes (10) | `data/benchmark_v2/consistency_routes.csv` |
| Phase-2 outputs (after the real run) | `data/benchmark_v2/gmaps/` (+ `figures/phase2/`) |
| Phase-3 outputs (after the real run) | `data/benchmark_v2/llm/` |
| Mock test outputs (git-ignored, not results) | `data/benchmark_v2/mock/` |
| Config (all thresholds) | `src/llm_benchmark/config.py` → section `V2` |
| Phase-1 script | `src/llm_benchmark/1b_build_od_pairs.py` |
| Phase-2 scripts | `src/llm_benchmark/4_query_gmaps_v2.py`, `4b_process_gmaps_v2.py` |
| Phase-3 scripts | `src/llm_benchmark/3_query_llm_v2.py`, `llm_clients.py`, `prompts/grounding_system_prompt.txt` |
| Shared helpers | `src/llm_benchmark/v2_common.py` |
| v1 (pilot) scripts and data, unchanged | `src/llm_benchmark/1_…6_*.py`, `data/benchmark/` |

## Scripts
| Command (run from `src/llm_benchmark/`) | Purpose | API calls? |
|---|---|---|
| `python 1b_build_od_pairs.py legs` | Hotspot-leg geometries from raw Stage-2 JSON | No |
| `python 1b_build_od_pairs.py geocode --dry-run` | Count calls + cost | No |
| `python 1b_build_od_pairs.py geocode [--only L07,L19]` | Landmark names → coordinates + checks | **Yes** (Places, cached) |
| `python 1b_build_od_pairs.py geocode --evaluate-only` | Re-run checks + apply `review_decisions.csv` | No |
| `python 1b_build_od_pairs.py pairs [--source approx\|geocoded]` | OSM routes, tags, balanced selection, plots | No |
| `python 4_query_gmaps_v2.py --dry-run` / `--status` | Count + cost + sample request / progress | No |
| `python 4_query_gmaps_v2.py [--limit N]` | Google predicted-traffic queries (28 per route) | **Yes** (Routes Pro) |
| `python 4b_process_gmaps_v2.py` | Offline: endpoints check, map-matching, final tags, plots | No |
| `python 3_query_llm_v2.py select-consistency` · `grounding-eval` · `status` | Offline helpers | No |
| `python 3_query_llm_v2.py grounding [--dry-run\|--limit N]` | Where-is-landmark check | **Yes** (Gemini) |
| `python 3_query_llm_v2.py benchmark --condition A\|B [--part main\|consistency\|all] [--dry-run\|--limit N]` | Benchmark queries | **Yes** (Gemini) |
| any of the above with `--mock` | Offline fake answers into `data/benchmark_v2/mock/` | No |

## Next steps (in order; 🛑 = Ishan decides / approves)
**🛑 Gate 3 — route list review** (Ishan + professor, using PHASE1_RESULTS.md). Changes → edit seed/decisions, rerun `pairs` (free).

**Decided 2026-10-01:** OPTIMAL routing (D-27), most-frequent-path tags (D-28), thinking A=LOW/B=HIGH (D-26), shuffled order (D-35), gemini-3.8-flash (D-36), endpoint tolerance (D-29).

**🛑 Still open:** reference week (D-37, holidays) · professor: prompt/schema tweaks in [IO_SPEC.md](IO_SPEC.md) §6.1 · grounding flag rule (coords AND locality?) · optional gemini-2.5-flash comparison · Batch API (50 % cheaper, ≤ 24 h).

**Phase 2 — Google ground truth** (code ready)
1. **🛑** `4_query_gmaps_v2.py --limit 1` — one real query, shown to Ishan (≈ $0).
2. **🛑** full run: 2,016 calls (list $20.16, expected $0 within 5,000 free/month). The reference week is fixed at the first real call.
3. `4b_process_gmaps_v2.py` (offline) → endpoint check, road sequences, final tags, group changes, plots q1–q7 → report to Ishan.

**Phase 3 — LLM, condition A** (code ready)
1. **🛑** Enable billing on the Gemini key (BILLING_AND_KEYS.md §A) — Ishan.
2. **🛑** 1 test call (`benchmark --condition A --limit 1`) → check thought tokens, model version, answer.
3. **🛑** grounding (64 calls ≈ $0.09) → `grounding-eval` (offline).
4. **🛑** condition A + consistency (2,576 calls ≈ $3.8, gemini-3.8-flash).

**Phase 4 — metrics** (`5_compare_results_v2.py`): log-ratio and absolute error (distance, time), over/under, medians; time-of-day sensitivity (LLM peak/night ratio vs Google's); traffic-awareness Spearman; road validity vs OSM names; Jaccard road overlap; repeat spread; naive baseline (straight line × 1.22 detour at per-slot typical speed); all split by band / road type / hotspot / slot / day; grounding-check failures reported separately.

**Phase 5 — charts + narrative** (`6_visualize_benchmark_v2.py`): log-scale scatters, time-of-day sensitivity plot, validity/overlap bars, error by group; findings vs midsem hypotheses; v1 as "pilot / lessons learned".

**Phase 3b — condition B (thinking on)** — last, costliest (≈ $19 with gemini-3.8-flash): **🛑 separate approval**.

**Later (optional):** condition C context ablation · OSM-Dijkstra ground truth (midsem idea) · other LLMs · MapmyIndia.
