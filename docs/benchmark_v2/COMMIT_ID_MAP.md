# Commit ID map — history cleanup of 2026-10-09 (R-45)

The unpushed history was rewritten to remove Google/LLM data files from old commits (D-62). Every commit was kept
(same message, author, date, order); only the IDs changed. Docs written before the cleanup quote the **old** IDs — use
this table to translate. Pre-cleanup backup: `~/Backups/Geospatial_MMI/repo_before_clean_*.bundle`.

benchmark-v2 (newest first). `main`: 0df60ba → 266c817.

| Old ID | New ID | Date | Message |
|---|---|---|---|
|  aa60cbf  | 33e2dda  |  2026-10-09 11:49  |  Professor update (2-page docx) + report figures script  |
|  34441c8  | 1e92b78  |  2026-10-09 11:30  |  docs: session context file + CLAUDE.md (auto-loaded context for future sessions)  |
|  c3c2c87  | 1767318  |  2026-10-08 21:18  |  docs: GitHub push plan (not executed)  |
|  515a0f2  | ea1161b  |  2026-10-08 21:18  |  docs: B/C deferred, ChatGPT plan, backups, iCloud conflict copies in .git  |
|  746c416  | d17bc24  |  2026-10-01 05:25  |  v2 Phase 4: LLM vs Google comparison (condition A) + findings  |
|  90cfb1b  | c237e37  |  2026-10-01 04:47  |  v2 docs: revert .nosync folder rename (app viewer cannot follow symlink)  |
|  c46949d  | bab772e  |  2026-10-01 04:41  |  v2 Phase 3 condition A complete (docs): PHASE3_RESULTS.md, run log, iCloud stall + .nosync folder  |
|  1b2c688  | bba3fab  |  2026-10-01 03:20  |  v2: shared LLM rate cap (60/min), 429 cool-down for all workers, stop after 10 consecutive failures  |
|  71bc3d7  | ae8b77b  |  2026-10-01 03:08  |  v2: Gemini live tests (prepay OK, 2.5-flash 404), measured token costs, professor Q13-Q15, grouping choice A  |
|  52c7317  | c3ac553  |  2026-10-01 02:58  |  v2: Phase 2 plots  |
|  1b7200d  | 7926bec  |  2026-10-01 02:58  |  v2 Phase 2 done: 2,016 Google queries processed; traffic index; PHASE2_RESULTS.md  |
|  aac7d55  | 540330f  |  2026-10-01 02:44  |  v2: fixes from first live tests (step-name parsing, map-matching flicker filter, plot guards, AFC disabled)  |
|  a08c606  | b25f3f5  |  2026-10-01 02:36  |  v2: condition-B approval guard; prepay facts (non-refundable, expiry, auto-reload off) in billing docs  |
|  6d90231  | c3e2844  |  2026-10-01 02:28  |  v2: --workers N parallel LLM requests (thread-safe writes, fatal stop); billing situation + prepay recommendation in docs  |
|  4ea17cf  | d57cc65  |  2026-10-01 02:06  |  v2: stop tracking Google/LLM-generated data (D-43); gemini-2.5-flash; grounding rule; Saturday-only holiday tag; PROFESSOR_DISCUSSION.md  |
|  8330cef  | ce02e99  |  2026-10-01 01:54  |  v2: clock time in prompt, schema field descriptions, pinned reference week 5-11 Oct with holiday tags; IMPORTANT_NOTES.md  |
|  ba2d858  | a01df4b  |  2026-10-01 01:39  |  v2: apply decisions (OPTIMAL, modal-path tags, gemini-3.8-flash A=LOW/B=HIGH, shuffled order, pinnable reference week); add IO_SPEC.md  |
|  233c3b4  | b0e5dc1  |  2026-09-30 23:22  |  v2 Phase 2 + 3 code (tested offline only, no API calls)  |
|  13b9cd3  | d704c75  |  2026-09-30 22:47  |  v2 Phase 1 complete: Gate-2 decisions, 66 landmarks, 72-route list, results doc  |
|  5a6ef56  | 3496d93  |  2026-09-30 22:21  |  v2: geocode 70 landmarks via Places (46 OK, 24 flagged); fix flags column clash  |
|  87e4358  | c08a26d  |  2026-09-30 22:03  |  v2: replace flyover landmarks, rename rough coordinate columns, log D-19..D-22  |
|  3e5837e  | 72d93c4  |  2026-09-30 20:30  |  v2 Phase 1: docs, landmark seed list, OD-pair builder (offline parts)  |
|  0df60ba  | 266c817  |  2026-09-30 20:03  |  Snapshot Stage 6 v1 benchmark before redesign  |
