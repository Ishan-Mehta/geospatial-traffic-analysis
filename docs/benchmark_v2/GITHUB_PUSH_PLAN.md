# Plan — handle Google data on GitHub and push safely (drafted 2026-10-08, NOT executed)

## Facts (checked 2026-10-08)
- Repo `Ishan-Mehta/geospatial-traffic-analysis` is **PUBLIC**; `origin/main` = commit 219d8fb.
- **Already public** (pushed long ago): `data/processed/geocoded_blr_roads_chain.csv`, `data/processed/geocoded_optimised_blr_roads.csv`
  (Google Geocoding coordinates of BBMP road waypoints) and `data/sample_response.json` (one Google Routes response).
- **Not pushed:** 1 commit on `main` (0df60ba, v1 snapshot) + 19 commits on `benchmark-v2`.
- Google/LLM data inside that **unpushed history** (removed from the current tip on 2026-10-01, but still in old commits):
  v1 — `data/benchmark/benchmark_routes*.csv`, `data/benchmark/llm_responses/*.jsonl`, `data/benchmark/test/*`;
  v2 — `data/benchmark_v2/cache/places/*.json` (72), `landmarks_geocoded.csv`, `landmarks_review.csv`, `candidate_pairs.csv`,
  `od_pairs.csv`, `od_pairs.geojson`, `hotspot_legs.geojson`, `rehearsal_approx/*`.
- **No API keys** in any commit of any branch (scan 2026-10-08). Full backup: `~/Backups/Geospatial_MMI/repo_all_branches_20261008.bundle`.
- iCloud created conflict copies inside `.git` (R-43) → a remote copy is also a corruption safeguard.

## Options
| | What | Effort | Risk |
|---|---|---|---|
| **A. Make the repo private, push as-is** | GitHub → Settings → Danger Zone → Change visibility → Private (Ishan), then push `main` + `benchmark-v2` | minutes | none for history; public visibility lost |
| **B. Stay public, clean first** | rewrite only the *unpushed* commits to drop the files above, verify, push; handle the 3 already-public files | ~1 h | low (unpushed history is safe to rewrite; backup exists) |
| C. Split | public code-only repo (cleaned) + private data (or data only in backups/Drive) | more | low |

## Steps for B (recommended if the repo must stay public)
1. Backups ✅ (bundle + data tarballs).
2. Install `git-filter-repo` (local tool), run on `main` + `benchmark-v2` **only for commits after origin/main**, removing the paths above
   (files stay on disk — they are git-ignored).
3. Verify: no listed path in `git log --all --name-only`; key scan = 0; `git fsck` clean; code/docs/figures/summaries intact; diff of
   the tip vs before = no change.
4. Already-public files — choose one:
   (i) **remove from the tip** (`git rm --cached`, add to `.gitignore`): stops further exposure; old public commits still contain them; or
   (ii) **purge from public history**: rewrite `main` and **force-push** — destructive for anyone who cloned/forked; GitHub may keep
   old commits reachable by hash until support purges caches. Only if the professor/institution requires it.
5. Push `main`, push `benchmark-v2` → open a PR `benchmark-v2 → main` → review → merge.
6. Optional: keep `.git` out of iCloud — rename `.git` → `.git.nosync` and create a `.git` *file* containing `gitdir: .git.nosync`
   (git supports this natively; no symlink, so the app's file viewer is unaffected).

Each step that changes GitHub (visibility, push, force-push) needs Ishan's explicit go.
