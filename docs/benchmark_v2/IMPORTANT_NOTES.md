# ⚠️ IMPORTANT — read before writing the report, sharing data, or publishing

Short list of things that are easy to forget and matter for correctness, fairness or compliance.
Details live in the linked docs; this page only collects the warnings.

## 1. Google data: storage, sharing and publication (compliance)
- Google Maps Platform content (Routes responses, Places/Geocoding results, **including coordinates**) is governed by the
  **Google Maps Platform Terms of Service and Service Specific Terms**. These restrict caching, storing and
  redistributing Google content (for several services, coordinates may only be cached temporarily — commonly cited as
  up to 30 days — while Place IDs may be stored). **Re-read the current terms before publishing**; they change.
- Google content we currently store locally (never commit it to a *public* repository without checking the terms):
  `data/benchmark_v2/cache/places/`, Google coordinates in `landmarks_geocoded.csv`, `candidate_pairs.csv`,
  `od_pairs.csv/.geojson`, `data/benchmark_v2/gmaps/` (after Phase 2), and the Stage-2 raw data in `data/raw/gmaps_data/`.
- **For the report / paper:** publish *derived* results (errors, ratios, correlations, aggregated maps), landmark
  **names**, and methodology — not bulk raw Google responses or Google coordinates. Cite Google Maps Platform (Routes API,
  predicted traffic) as the ground-truth source.
- **Ask the professor** (and, if needed, the institution) before sharing the dataset or making the repo public.
- **Git policy (D-43):** Google- and LLM-generated data is git-ignored and never committed. The GitHub repo is **public**;
  earlier local (unpushed) commits on `main`/`benchmark-v2` still contain some of that data → **rewrite history or make the
  repo private before any push.** Already public since earlier pushes: `data/processed/geocoded_*.csv` (Google geocoding
  coordinates) and `data/sample_response.json` (a Google Routes response) — decision pending with the professor.
- **Backup:** because this data is not in git, keep a separate local/cloud copy of `data/benchmark_v2/` (re-creating it
  would cost API calls).
- After the project, consider deleting/refreshing stored Google content in line with the terms.

## 2. What the Google numbers mean
- Ground truth = **predicted typical traffic** for future departure times (`TRAFFIC_AWARE_OPTIMAL`, `trafficModel BEST_GUESS`),
  **not live traffic**. Say "Google's predicted travel time" in the report. (D-08, D-27)
- Reference week: **Mon 5 – Sun 11 Oct 2026**. **Sat 10 Oct = Mahalaya Amavasya (public holiday)** — tagged in
  `calendar_note`; the LLM is told only "Saturday", so report Saturday results **with and without** it. Sun 11 Oct
  (Navaratri begins) is deliberately not tagged — kept as a normal weekend day. (D-37)
- Google run completed 2026-10-01 (2,016/2,016).
- **staticDuration ≠ free-flow:** Google's staticDuration is the ETA from historical traffic only. Never call
  duration/static "congestion vs free-flow"; use the traffic index (duration ÷ route's fastest of 28 queries). (D-48)
- Final tags (from Google paths) are **unbalanced** (43 arterial / 17 mixed / 12 sub-arterial) — see D-49.

## 3. What the LLM numbers mean
- Condition A = **lowest thinking level** (`LOW` on gemini-3.8-flash), **not "no thinking"** — Gemini 3.x cannot disable
  thinking. Thought tokens are logged per answer; report them. (D-26)
- v2 prompt/schema differ slightly from the v1 pilot: clock time appended ("Evening Rush (18:00)", D-38) and one-line
  field descriptions (D-39). **v1 pilot answers are not directly comparable** with v2.
- Each call is independent (stateless); queries run in a shuffled order; `model_version` is logged — check it did not
  change mid-run. (D-35)
- Grounding-flagged routes (LLM misplaces a landmark by > 2 km) are **flagged, not removed** — report separately. (D-34)

## 4. Labels and groups
- Final tags come from **Google's most frequent path** (Phase 2); Phase-1 tags were provisional (OSM). Report how many
  routes changed group. (D-28)
- "High/low hotspot exposure" is **relative** (above/below the band median), not absolute. (D-17)
- With 4 routes per group, compare **one factor at a time** (24 per band, 24 per road type, 36 per exposure level);
  18-cell tables are descriptive only.
- Stage-4 "congestion ratio" is negative for 588/689 legs (inflated leg-level static duration) — do not quote Stage-4
  congestion ratios without that caveat. (AUDIT_v1 §1.4)

## 5. Money and accounts
- Every paid batch: dry-run → approval → run (D-14). Gemini **paid tier**: prompts not used for training; the free tier
  may be. gemini-3.8-flash price **doubles on 2027-01-01** → finish LLM runs in 2026. (D-36)
- API keys live only in `.env` (git-ignored); scripts never print them.

## 6. Test data
- Everything under `data/benchmark_v2/mock/` and `rehearsal_approx/` is **test output, not results**.
