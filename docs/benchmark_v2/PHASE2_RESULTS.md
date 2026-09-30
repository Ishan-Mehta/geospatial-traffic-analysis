# Phase 2 results — Google ground truth (2026-10-01)

**Status:** complete. 2,016 / 2,016 queries answered, 0 errors. Data (local only, git-ignored, D-43):
`data/benchmark_v2/gmaps/` · plots: `data/benchmark_v2/figures/phase2/` · runs R-25…R-29 in [RUN_LOG.md](RUN_LOG.md).
Semantics: **Google's predicted typical traffic** for the week Mon 5 – Sun 11 Oct 2026 (`TRAFFIC_AWARE_OPTIMAL`).

## 1. Summary
| Item | Result |
|---|---|
| Queries | 72 routes × 7 days × 4 slots = **2,016**, all OK (≈ 20 min, Pro SKU, within free cap) |
| Distance (primary route) | 1.3 – 28.9 km, median 10.7 km |
| Predicted duration | 6.3 – 84.5 min, median 29.6 min |
| Alternatives returned | 3 routes for 1,511 queries, 2 for 412, 1 for 93 |
| **Endpoint check** (same origin/destination) | **100 %** within tolerance; median offset 10 m, max 83 m |
| Map-matching quality | median 3.1 % of the route unmatched (90th percentile 12 %); median 12 OSM roads per route |
| Path stability | Google used 1 path in all 28 queries for 38 routes, 2 paths for 27, 3 for 7 |
| Peak ÷ night duration | weekday median **1.33**, weekend 1.16 |
| Busiest time | weekday **18:00** (traffic index ≈ 1.6); fastest: Sunday 08:00 (28 routes) or Monday 23:00 (25) |

## 2. Traffic pattern (plot q2) — median traffic index (duration ÷ the route's fastest of its 28 queries)
| Slot | Mon | Tue | Wed | Thu | Fri | Sat | Sun |
|---|---|---|---|---|---|---|---|
| 08:00 Morning Rush | 1.20 | 1.19 | 1.19 | 1.18 | 1.17 | 1.08 | 1.01 |
| 14:00 Off-Peak | 1.32 | 1.35 | 1.38 | 1.37 | 1.34 | **1.47** | 1.27 |
| 18:00 Evening Rush | 1.58 | 1.60 | **1.62** | 1.60 | 1.61 | 1.55 | 1.31 |
| 23:00 Night | 1.01 | 1.03 | 1.06 | 1.05 | 1.12 | 1.11 | 1.05 |
Observations: 08:00 is only mildly congested (Bangalore's morning peak is later); 14:00 is busier than 08:00; the
evening peak dominates; Saturday 14:00 (the Mahalaya Amavasya holiday) is the busiest midday — to be read with the
holiday caveat (IMPORTANT_NOTES §2).

## 3. Two methodological findings
1. **Google's `staticDuration` is not free-flow time.** Google defines it as the ETA "considering only historical traffic
   information". Median duration/static is < 1 at night (0.86) and at 08:00 (0.94). The same field made most Stage-4
   congestion ratios negative (AUDIT_v1 §1.4). → Traffic is measured with the **traffic index** instead (D-48).
2. **Google's routes differ systematically from the OSM shortest paths used for provisional tags.** Google optimises time,
   so it uses more main roads (median arterial share 0.50 → **0.65**), runs more along volatile corridors (median hotspot
   share **0.74**) and is ~8 % longer. Result: **48 of 72 routes changed group** (band 13, road type 35, exposure 19).

## 4. Final tags (from Google's most frequent path) — the groups are now unbalanced
| | arterial | mixed | sub-arterial | total |
|---|---|---|---|---|
| 1–5 km | 7 | 4 | 6 | 17 |
| 5–12 km | 15 | 8 | 4 | 27 |
| 12–25 km (+3 routes of 25–29 km) | 21 | 5 | 2 | 28 |
| **total** | **43** | **17** | **12** | 72 |
Hotspot exposure (Phase-1 band medians applied to Google shares): high 49, low 23.
Continuous measures still span wide ranges: arterial share 0.00–0.98 (quartiles 0.47 / 0.65 / 0.78), hotspot share
0.09–1.00 (0.50 / 0.74 / 0.91). → **Decision needed** on how to group (see README / D-49).

## 5. Figures (`figures/phase2/`)
q1 Google vs OSM length · q2 traffic-index heatmap (table above) · q3 duration by slot per band, weekday vs weekend ·
q4 tag changes + final band × road type · q5 endpoint offsets · q6 path stability · q7 peak/night ratio by band.
