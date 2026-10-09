# Session context: everything so far (for Claude and for Ishan)

Last updated: **2026-10-09**. This is a plain-language summary of the long working session (30 Sep – 9 Oct 2026) that
rebuilt Stage 6 of the project. **Read this first in any new session.** Details live in the other docs in this folder
(list at the end). The exact numbers are in the results docs; this file explains them and the reasons behind them.

---
## 1. Who and what
- **Ishan Mehta.** Student project supervised by **Prof. Vinayak Naik**. Repo: `~/Desktop/Projects/Geospatial_MMI`
  (GitHub `Ishan-Mehta/geospatial-traffic-analysis`, which is **public**). Work branch: **`benchmark-v2`**.
- **Research question (midsem report):** can LLMs do reliable geospatial reasoning, i.e. find the shortest or fastest path
  between two places in Bangalore, compared with navigation tools (Google Maps; MapmyIndia was planned)?
- **Working title for the professor update:** "Benchmarking LLMs against Navigation tools".
- **Stages 1–5 (done before this session):** BBMP road list → geocoding → a Google Routes scrape every 2 h for 7 days
  (April 2026, raw data in `data/raw/gmaps_data/`, 1.6 GB) → flattening → statistics (`output/`). Stage 6 = the LLM benchmark.

## 2. How Ishan likes to work (important)
- Go **step by step**. Stop only when Ishan really has to decide or review something, not after routine work.
- **Explain in simple words**, with no unexplained jargon, and **define terms**. He dislikes vague questions.
- **Ask before any paid API batch**, and give the call count and cost (USD and ₹) first. Offline scripts and file edits
  don't need permission.
- **Document everything** in `docs/benchmark_v2/` without repeating the same thing in several places.
- **Commit locally whenever useful. Never push** without his explicit go. **Never delete data** (move to backup instead).
- **Never commit Google- or LLM-generated data** (Google's terms of use, size). Raw data is git-ignored.
- Vocabulary: **route** = one landmark → landmark pair. **Query** = one route at one time slot on one day
  (28 per route = 4 slots × 7 days).

## 3. Why v1 was thrown away (Phase 0 audit, `AUDIT_v1.md`)
The old benchmark used 14 tiny road segments (10 under 1.5 km), with vague names produced by reverse geocoding
("Start of X → End of X"). Two routes came from geocoding mistakes, and only **1 of 22** LLM answers had actually been
saved. v1 is kept unchanged as a "pilot / lessons learned" item; the snapshot is commit `0df60ba` on `main`.

## 4. What v2 did, phase by phase
| Phase | What | Key result |
|---|---|---|
| 1 Routes | 70 landmarks (metro stations, junctions, hospitals, tech parks…), each name looked up once in Google Places (name → coordinates, cost $0), automatic checks + Ishan's review → **66 landmarks** → **72 routes** balanced by length, road type and "hotspot exposure" | `PHASE1_RESULTS.md` |
| 2 Google | Google Routes `TRAFFIC_AWARE_OPTIMAL`, future week **5–11 Oct 2026**, 08:00/14:00/18:00/23:00 every day → **2,016 queries**, 0 errors, $0. Google's route lines matched onto OSM to get road names | `PHASE2_RESULTS.md` |
| 3 LLM | **gemini-3.8-flash**, zero context, thinking **LOW** (condition A), same 2,016 queries + 560 repeat answers + 64 "where is this landmark?" checks. Cost **$1.83** (prepay ₹700, ≈ ₹540 left) | `PHASE3_RESULTS.md` |
| 4 Compare | distance/time errors, time-of-day behaviour, traffic labels, road names, consistency, naive formula baseline, with proper uncertainty | `PHASE4_RESULTS.md`, `FINDINGS_AND_INTERPRETATION.md` |

The LLM gets the landmark's **name**; Google gets the same landmark's **coordinates**, so both answer the same trip
(Google's start/end points were a median of 10 m from ours).

## 5. Main findings (simple version; details in FINDINGS_AND_INTERPRETATION.md)
1. Gemini **knows all the landmarks** (median 248 m off) and **names real roads** (≥ 95 % real).
2. **Distances are good** (≈ 6 % too long). **Times are off by time of day:** +42 % at 08:00, +31 % at 18:00, about right
   at 14:00, −13 % at night.
3. **Headline:** it knows *when* traffic is bad, but **exaggerates rush hour** (peak ÷ night = 2.15 vs Google's 1.34) and
   applies the **same ~2× to every route**. So it has a city-wide stereotype, not route-specific knowledge.
4. It knows the main corridors but only **22 % of the roads on Google's route**.
5. **Short routes (1–5 km) are hardest.** "Sub-arterial routes are worse" is mostly a length effect; the gap that remains
   is in *which roads* it knows.
6. A **simple formula** (straight line × 1.22 ÷ typical speed) is about as accurate (the formula knows exact coordinates).
7. Answers are **stable** (3–4 % spread between repeats).
- Midsem hypotheses: H1 (better on arterials) partly supported · H2 (poor time estimation) supported with nuance ·
  H3 (context helps) and H4 (India-specific) not tested yet.
- Extra finding: Google's `staticDuration` is **not** empty-road time (it's a historical-traffic estimate) → we use a
  "traffic index" instead. Google's fastest routes use main roads far more than the shortest-distance paths.

## 6. Important decisions (full log: DECISIONS.md, D-01…D-61)
- Forward geocoding name → coordinate (D-02). Bands 1–5 / 5–12 / 12–25 km (D-03). Road type from OSM road classes (D-04).
- Hotspot exposure is **relative** (above/below the band median) (D-17). Final route tags come from Google's
  **most frequent path** (D-28).
- Grouping is now unbalanced (43 arterial / 17 mixed / 12 sub-arterial) → **option A chosen for now**: keep the 72
  routes and use continuous measures (D-49).
- Prompt = the professor's v1 prompt + clock time, e.g. "Evening Rush (18:00)" (D-38), and the JSON schema with one-line
  field descriptions (D-39). The professor should be told about D-38 and D-39.
- Reference week 5–11 Oct; **Saturday 10 Oct holiday tagged**, Sunday not (D-37).
- **Conditions B (high thinking) and C (context): deferred** to the next round, to agree with the professor (D-60).
  Condition B is code-locked to ≤ 3 test calls without `--approved-by-ishan` (D-46).
- **A ChatGPT model is coming from the professor** → add it via the OpenAI adapter stub in `llm_clients.py` (D-61).
  Needs: model name, key in `.env`, reasoning setting, price.
- gemini-2.5-flash is **not available** to our key (404). No second Gemini model for now.

## 7. Environment and gotchas
- venv: `source maps_venv/bin/activate`; scripts are in `src/llm_benchmark/` (v2: `1b_build_od_pairs.py`,
  `4_query_gmaps_v2.py`, `4b_process_gmaps_v2.py`, `3_query_llm_v2.py`, `llm_clients.py`, `5_compare_results_v2.py`,
  `v2_common.py`; all settings in `config.py`, section V2).
- **iCloud syncs the Desktop.** It caused (a) scripts hanging at 0 % CPU for minutes (Python waiting on file reads), and
  (b) **conflict copies inside `.git`** ("benchmark-v2 2", "index 2"…) that broke git. These were moved to the backup
  folder. A `.nosync` folder rename was tried and **reverted** (the app's file viewer can't follow symlinks). If things
  hang, suspect iCloud; Phase 4 was run from a scratch copy outside iCloud.
- Gemini key = "My First Project" (prepay). Maps key works (free monthly allowance). Keys only in `.env`; never print them.
- **Backups** (outside iCloud): `~/Backups/Geospatial_MMI/`: data tarballs (`benchmark_v2`, `raw`), a full git bundle,
  the manifest, and the moved iCloud conflict copies.

## 8. Where things stand (2026-10-09)
- Done: Phases 0–4 for condition A; all docs; backups. **History cleaned 2026-10-09 (D-62, R-45)** — commit IDs changed;
  docs quote some *old* IDs → see `COMMIT_ID_MAP.md`. **Nothing pushed yet**; Ishan reviews the history, then we push.
- **GitHub (GITHUB_PUSH_PLAN.md):** already-public files (2 geocoded CSVs + `sample_response.json`): Ishan says
  **leave them**. Unpushed history now **cleaned** (D-62) — next: Ishan checks history → push `main` + `benchmark-v2`. Unpushed commits contain Google/LLM data in older commits. Ishan is OK with cleaning them **only if the
  commit history is kept**. A rewrite with `git filter-repo` keeps every commit (messages, dates, order); only the data
  files disappear from them and the commit IDs change. Awaiting his go.
- **Task 1 — DRAFT READY (R-44):** `docs/benchmark_v2/report/Professor_Update_Oct2026.docx` (2 pages; rebuild with
  `node report/build_update_docx.js <out.docx> report/figures`, needs `npm install docx`). Original brief: **a 1–2 page update for Prof. Naik**, in a light, easy tone, as a Google Doc (Claude builds a
  `.docx` → Ishan uploads it to Google Drive → opens in Google Docs → exports PDF). Title "Benchmarking LLMs against
  Navigation tools", by Ishan Mehta, for Prof. Vinayak Naik. Mention v1 briefly. Claude chooses the figures (Ishan hasn't
  read the findings yet and wants them explained later).
- **Task 2 (later):** add the LLM benchmarking phase to the midsem report (Google Docs), either via Chrome or as
  paste-ready text. To discuss.
- Later: explain the findings to Ishan in detail; Phase 5 report figures; condition B/C and ChatGPT after the
  professor's input; professor questions in PROFESSOR_DISCUSSION.md (15).

## 9. Doc map (docs/benchmark_v2/)
README (status, file locations, next steps) · **SESSION_CONTEXT (this file)** · FINDINGS_AND_INTERPRETATION · PHASE1–4_RESULTS ·
METHODOLOGY (definitions) · DECISIONS (D-xx) · RUN_LOG (R-xx) · DATA_DICTIONARY · IO_SPEC (exact prompts and requests) ·
CODE_GUIDE_PHASE2_3 · BILLING_AND_KEYS · IMPORTANT_NOTES (caveats, data terms) · PROFESSOR_DISCUSSION · GITHUB_PUSH_PLAN · AUDIT_v1.
