# Geospatial MMI: notes for Claude

**Start here:** read `docs/benchmark_v2/SESSION_CONTEXT.md` (the full context of the work so far), then
`docs/benchmark_v2/README.md` (status, file locations, next steps).

Project: Bangalore traffic pipeline (Stages 1–5) plus **Stage 6: benchmarking LLMs against Google Maps** (branch
`benchmark-v2`). Owner: Ishan Mehta. Supervisor: Prof. Vinayak Naik.

## Rules
- Work step by step. Explain simply and define terms. Stop only for real decisions or reviews.
- **Ask before any paid API calls** (Google Routes/Places, Gemini, OpenAI); show the call count and cost first.
- **Never push** to GitHub without explicit approval (the repo is public). Commit locally when useful.
- **Never delete data**; move it to `~/Backups/Geospatial_MMI/` instead.
- **Never commit Google- or LLM-generated data** (git-ignored; see D-43 in `docs/benchmark_v2/DECISIONS.md`).
- Never print or commit API keys (`.env` only).
- Document decisions in `DECISIONS.md`, runs in `RUN_LOG.md`, results in the `PHASE*_RESULTS.md` files.

## Environment
- venv: `source maps_venv/bin/activate`; v2 scripts: `src/llm_benchmark/*_v2.py`, `llm_clients.py`, `v2_common.py`;
  settings: `config.py` (V2 section).
- The folder is synced by **iCloud**. If a script sits at 0 % CPU for minutes, or git reports "bad object … 2", that's
  iCloud. See SESSION_CONTEXT §7.
