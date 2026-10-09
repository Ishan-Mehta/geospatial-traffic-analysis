# Stage 6 v2 — LLM vs Google Maps routing benchmark

Branch: `benchmark-v2` · v1 snapshot: commit `0df60ba` on `main` · outputs: `data/benchmark_v2/`

## Read in this order
| Doc | What it holds (single source of truth for…) |
|---|---|
| [report/Professor_Update_Oct2026.docx](report/Professor_Update_Oct2026.docx) | 📄 **2-page update for Prof. Naik** (upload to Google Drive → Google Docs → PDF) |
| [SESSION_CONTEXT.md](SESSION_CONTEXT.md) | 🧭 **Full context of the work so far, in plain words** (start here in a new session) |
| [PROFESSOR_DISCUSSION.md](PROFESSOR_DISCUSSION.md) | **Questions for the professor** (summary first, details after) |
| [GITHUB_PUSH_PLAN.md](GITHUB_PUSH_PLAN.md) | Plan for the public-repo data issue and a safe push (not executed) |
| [IMPORTANT_NOTES.md](IMPORTANT_NOTES.md) | ⚠️ **Read first** — data-use/compliance, what the numbers mean, caveats for the report |
| [PHASE1_RESULTS.md](PHASE1_RESULTS.md) | **The 72-route list + Phase 1 summary** (for Ishan / professor) |
| [FINDINGS_AND_INTERPRETATION.md](FINDINGS_AND_INTERPRETATION.md) | ⭐ **What the study found and what it means** (for the report) |
| [PHASE4_RESULTS.md](PHASE4_RESULTS.md) | **LLM vs Google comparison — all numbers and plots** |
| [PHASE3_RESULTS.md](PHASE3_RESULTS.md) | **LLM results so far** (grounding, condition A, consistency, cost, first comparison) |
| [PHASE2_RESULTS.md](PHASE2_RESULTS.md) | **Google ground-truth results** (2,016 queries) |
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
| 2 Google ground truth | ✅ **2,016/2,016 done** (0 errors), processed; results in PHASE2_RESULTS.md · 🛑 grouping decision D-49 |
| 3 LLM queries (gemini-3.8-flash) | ✅ grounding 64/64 · condition A 2,016/2,016 + consistency 560/560 · cost $1.83 — PHASE3_RESULTS.md |
| 3b condition B / C | ⏸️ deferred to next round, to agree with professor (D-60); B = 1 test call so far |
| ChatGPT model | ⏳ awaiting model/key from professor; OpenAI adapter stub ready (D-61) |
| 4 Metrics | ✅ done (condition A) — PHASE4_RESULTS.md, FINDINGS_AND_INTERPRETATION.md |
| 5 Report charts + narrative | ⏭️ next (offline) |

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
| Phase-3 outputs | `data/benchmark_v2/llm/` |
| Phase-4 outputs | `data/benchmark_v2/results/` (summaries committed) + `figures/phase4/` |
| ⚠️ Git policy | Google/LLM-generated files are git-ignored (D-43) — back them up separately |
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
| `python 5_compare_results_v2.py [--model KEY --condition A]` | Phase 4 comparison, tables, plots | No |
| `python 3_query_llm_v2.py grounding [--dry-run\|--limit N]` | Where-is-landmark check | **Yes** (Gemini) |
| `python 3_query_llm_v2.py benchmark --condition A\|B [--part main\|consistency\|all] [--dry-run\|--limit N] [--workers 4]` | Benchmark queries (parallel option) | **Yes** (Gemini) |
| any of the above with `--mock` | Offline fake answers into `data/benchmark_v2/mock/` | No |

## Next steps (in order; 🛑 = Ishan decides / approves)
**🛑 Gate 3 — route list review** (Ishan + professor, using PHASE1_RESULTS.md). Changes → edit seed/decisions, rerun `pairs` (free).

**Decided 2026-10-01:** OPTIMAL routing (D-27), most-frequent-path tags (D-28), thinking A=LOW/B=HIGH (D-26), shuffled order (D-35), gemini-3.8-flash (D-36), endpoint tolerance (D-29), reference week 5–11 Oct with Saturday holiday tag (D-37), clock time in prompt (D-38), schema descriptions (D-39), no extra field (D-40), gemini-2.5-flash as second model (D-42), grounding rule coords AND locality (D-34), no Google/LLM data in git (D-43).

**⏰ Deadline:** the Google run must finish **before Mon 5 Oct 2026, 07:30 IST** (else week of 26 Oct).

**🛑 Still open:** professor items ([PROFESSOR_DISCUSSION.md](PROFESSOR_DISCUSSION.md)) · Batch API (Ishan: maybe tomorrow) · no push for now (history contains Google data; repo is public).

**Gemini billing (D-45, pending):** *My First Project* → Set up prepay (≈ ₹700; non-refundable, expires in 1 year, auto-reload OFF; check it doesn't share the Maps billing account) → its key into `.env` → 1 test call. Condition B is code-locked to ≤ 3 test calls without `--approved-by-ishan` (D-46). Current `.env` key = Default Gemini Project (free tier).

**Estimated run time (4 workers, capped at 60 requests/min, D-52):** grounding ~1 min · 3.8-flash A main ~35 min · consistency ~10 min · 3.8-flash B ~35–60 min (if approved). Google already done.

**First live tests (≈ 7 paid calls, cents; each needs Ishan's go):** (1) Google `--limit 1` → inspect raw JSON; (2) `4b` on it (offline) → check endpoints, road sequence; (3) Gemini: `grounding --limit 1`, `benchmark --condition A --limit 1` for gemini_38_flash and gemini_25_flash, `--condition B --limit 1` for gemini_38_flash (measures thinking tokens) → inspect answers, model versions, token counts; (4) re-estimate costs from the real token counts.

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
