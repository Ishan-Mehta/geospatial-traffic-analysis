# Decision log (v2)

Format: **D-nn · date · decision** — why · alternatives rejected · approved by.
Definitions referenced here live in [METHODOLOGY.md](METHODOLOGY.md).

| ID | Date | Decision | Why | Alternatives rejected | Approved |
|---|---|---|---|---|---|
| D-01 | 2026-09-30 | v1 kept untouched (commit `0df60ba` on `main`); v2 on branch `benchmark-v2`, outputs in `data/benchmark_v2/` | Revertible; v1 becomes the "pilot" section | Edit v1 in place | Ishan |
| D-02 | 2026-09-30 | Route endpoints are **new landmarks, forward-geocoded (name → coordinate)** | v1's reverse geocoding produced vague/wrong names (AUDIT_v1 §1.2–1.3) | Reverse-geocode old legs; nearest-landmark to old coordinates | Ishan |
| D-03 | 2026-09-30 | Distance bands 1–5, 5–12, 12–25 km; routes < 2 km only between compact landmarks | Ishan wanted the short end included; the compact rule stops landmark size dominating short routes | 2 km minimum; 0.5 km minimum | Ishan |
| D-04 | 2026-09-30 | Road type from **OSM `highway` tags** (arterial / mixed / sub-arterial); mixed kept as a group | BBMP list geocoding was unreliable; OSM tags are consistent citywide | BBMP A/S name matching; dropping mixed routes | Ishan |
| D-05 | 2026-09-30 | Hotspot = top-20 % CV of live duration among 564 plausible Stage-4 legs | Congestion ratio negative on 588/689 legs (inflated static baseline) | Congestion-ratio ranking; all 689 legs | Claude (proposed in plan, plan approved) |
| D-06 | 2026-09-30 | As many routes as good landmarks allow: target ~72, minimum 54, balanced over 18 groups | "More routes is better"; balance prevents one kind dominating | 36 routes; all pairs (~100 k LLM calls) | Ishan |
| D-07 | 2026-09-30 | 28 queries per route: 4 slots × 7 days (Mon–Sun) | Full-week coverage requested | Wed + Sat only (v1) | Ishan |
| D-08 | 2026-09-30 | Google ground truth = **predicted typical traffic** via future `departureTime`, all queried at once; labelled as predicted | Reproducible, minutes not a week | Live over a real week; both | Ishan |
| D-09 | 2026-09-30 | 1 query = 1 Google call + 1 LLM call (condition A). Condition B (thinking on) = second LLM call per query, run **last** after separate approval. Consistency subset: 10 routes × 2 extra A samples | Cost control; B is the most expensive part | 3 repeats × A & B for all | Ishan |
| D-10 | 2026-09-30 | LLM grounding check once per landmark (separate prompt) | Separates "didn't know the place" from "routed badly" | None | Ishan |
| D-11 | 2026-09-30 | No via points on either side | The test is whether the LLM *chooses* a sensible route | Pass Google's via points to LLM | Ishan |
| D-12 | 2026-09-30 | LLM layer provider-agnostic (config registry + adapters); Gemini implemented first | Compare other LLMs later without code changes | Gemini-only code | Ishan |
| D-13 | 2026-09-30 | Prompt wording + JSON schema unchanged from v1; only origin/destination strings and weekday names change | Professor's requirement | — | Professor / Ishan |
| D-14 | 2026-09-30 | Every paid batch: `--dry-run` (count + cost) → explicit approval → run | Budget safety | — | Ishan |
| D-15 | 2026-09-30 | Seed landmarks carry an approximate coordinate written by Claude; used only as an independent check (> 2 km → flag) and for an offline rehearsal of Phase 1b. **Never sent to Google or the LLM, never used in results** | Cheap cross-check against wrong namesakes; lets the pairing code be tested before paying for geocoding | No cross-check | Claude (pending Ishan's Gate-1 review) |
| D-16 | 2026-09-30 | Landmark `kind` limited to places inside the local OSM graph extent (≈ BBMP limits: lat 12.835–13.142, lng 77.460–77.777); airport and far-periphery sites excluded | Provisional OSM routing and snapping need the graph | Download a larger OSM graph | Claude (pending Ishan's Gate-1 review) |
| D-17 | 2026-09-30 | Hotspot tag changed from absolute "≥ 300 m overlap" to **relative exposure**: high if hotspot share ≥ per-band median | In the offline rehearsal 98.5 % of candidates met the 300 m rule (hotspot legs cover ≈ 603 km, most arterials), so "hot" just meant "uses a main road" and 5 of 18 groups were empty. Median split gives balanced, meaningful high/low exposure | Absolute threshold; stricter CV cut (top 5 %) — still corridor-dominated | Claude (reported to Ishan at Gate 1) |
| D-18 | 2026-09-30 | Snap landmarks to the largest strongly connected component of the OSM graph | Trinity Circle snapped to an isolated one-way fragment → 35 pairs had no path | Snap to any node | Claude (bug fix) |
| D-19 | 2026-10-01 | Flyover landmarks replaced by ground-level places: Hebbal Flyover → Esteem Mall Hebbal (L14); Domlur Flyover → Embassy GolfLinks Business Park (L39) | A flyover point may sit on the elevated deck; hard to pin to a ground road | Keep flyovers | Ishan |
| D-20 | 2026-10-01 | Seed coordinate columns renamed `rough_lat/rough_lng`; they are Claude's from-memory estimates (errors of a few hundred m up to ~1 km observed, e.g. Hennur Cross ~700 m) and only back a 2 km sanity check | Ishan found 300–700 m discrepancies; name makes their role explicit | Tighten threshold (would false-flag) | Ishan / Claude |
| D-21 | 2026-10-01 | Places Text Search (New) first, Geocoding API only as fallback; each landmark geocoded once, raw responses cached, results stored in `landmarks_geocoded.csv` | Places is built for named places and returns name/type/multiple candidates needed for the checks; Geocoding is address-oriented and often returns area/road centroids | Geocoding first | Ishan |
| D-22 | 2026-10-01 | LLM names kept as drafted (Forum Mall name either way) | Ishan: not sure names can be improved; fine as is | — | Ishan |
