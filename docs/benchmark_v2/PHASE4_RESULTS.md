# Phase 4 results — LLM (gemini-3.8-flash, condition A) vs Google Maps (2026-10-01)

**Status:** complete for condition A. Script `src/llm_benchmark/5_compare_results_v2.py` (offline, 25 s).
Aggregate tables: `data/benchmark_v2/results/summary_*.csv` (committed) · per-query / per-route tables git-ignored (D-43) ·
figures `data/benchmark_v2/figures/phase4/r01…r11`. Metric definitions: [METHODOLOGY.md](METHODOLOGY.md) §7.
Interpretation for the report: [FINDINGS_AND_INTERPRETATION.md](FINDINGS_AND_INTERPRETATION.md).

Numbers are for **sample 0** (one answer per query): 72 routes × 28 queries = **2,016 comparisons**; all endpoints OK;
0 routes flagged by the grounding check. "Ratio" = LLM ÷ Google; medians with 95 % route-level bootstrap CIs.

## 1. Headline numbers
| Measure | Result |
|---|---|
| Distance ratio (median) | **1.06** [1.04 – 1.12] · median abs. % error 13 % · LLM longer than Google in 69 % of queries |
| Time ratio (median) | **1.12** [1.04 – 1.14] · median abs. % error 21 % · median abs. error 5.8 min · LLM slower in 63 % |
| Time ratio by slot | 08:00 **1.42** [1.38–1.53] · 14:00 0.99 [0.95–1.04] · 18:00 **1.31** [1.24–1.38] · 23:00 **0.87** [0.85–0.91] |
| Time ratio weekday / weekend | 1.17 / 1.02 (Saturday holiday 1.06 · Sunday 1.00) |
| **Time-of-day sensitivity** (weekday peak ÷ night, per route, median) | LLM **2.15** vs Google **1.34** → LLM exaggerates by ×1.6 |
| …does the LLM know *which* routes are peak-sensitive? | Spearman across routes **−0.24** → no |
| …does it order a route's 28 times correctly? | within-route Spearman median **0.73** → mostly yes |
| Traffic label vs Google traffic index | Spearman **0.63** overall; within a slot: 08:00 0.66 · 18:00 0.47 · 14:00 0.17 · 23:00 0.03 |
| Road names that are real Bangalore roads | **95 %** per answer (lower bound; reference = OSM + Google + BBMP names) |
| Overlap with Google's roads | Jaccard **0.19** · recall of Google's roads **22 %** · 57 % of LLM roads are on Google's route |
| Naive baseline (straight line × 1.22 at Stage-2 speed per slot) | better than the LLM on median error: time 0.17 vs 0.21, distance 0.10 vs 0.13 (abs. log ratio); LLM wins 44 % (time) / 51 % (distance) of queries |
| Consistency (3 samples, 280 queries) | CV distance 2.7 % · time 3.8 % · same label 96 % · road-list Jaccard between samples 0.50 |
| Grounding | 0 of 64 landmarks misplaced (median 248 m) |

## 2. Time of day (plots r03, r04, r05; `summary_time_of_day.csv`)
Median time relative to the route's weekday-night time:
| | 08:00 | 14:00 | 18:00 | 23:00 |
|---|---|---|---|---|
| Weekday — Google | 1.13 | 1.25 | 1.50 | 1.00 |
| Weekday — LLM | **1.98** | 1.45 | **2.32** | 1.00 |
| Weekend — Google | 0.99 | 1.24 | 1.30 | 1.02 |
| Weekend — LLM | 1.30 | 1.37 | 1.86 | 0.98 |
The LLM labels **92 %** of weekday 08:00 queries and **100 %** of weekday 18:00 queries "heavy", 0 % at 14:00 and 23:00.
Google's 08:00 is only mildly congested (index 1.19): Bangalore's morning peak is later than 08:00; the LLM treats
"Morning Rush (08:00)" as full rush hour.

## 3. Traffic labels (plot r06; `summary_traffic_labels.csv`)
| LLM label | n | Google traffic index, median [IQR] |
|---|---|---|
| none | 4 | 1.04 [1.01–1.09] |
| light | 596 | 1.06 [1.02–1.14] |
| moderate | 639 | 1.32 [1.23–1.43] |
| heavy | 777 | 1.44 [1.21–1.65] |
Labels are monotone with real traffic, but mostly determined by the time slot (within-slot correlation is low).

## 4. By route group (plot r07; `summary_by_group.csv`, `summary_group_tests.csv`, `summary_length_controlled.csv`)
| Group | Routes | Distance ratio | Time ratio | Time abs. % error | Road Jaccard | Road validity |
|---|---|---|---|---|---|---|
| 1–5 km | 17 | 1.13 | 1.22 | 34 % | 0.18 | 0.95 |
| 5–12 km | 27 | 1.04 | 1.13 | 20 % | 0.22 | 0.95 |
| 12–25+ km | 28 | 1.08 | 1.07 | 17 % | 0.16 | 0.95 |
| arterial | 43 | 1.05 | 1.12 | 19 % | 0.21 | 0.96 |
| mixed | 17 | 1.08 | 1.09 | 23 % | 0.20 | 0.95 |
| sub-arterial | 12 | 1.15 | 1.15 | 24 % | **0.11** | 0.93 |
| high hotspot exposure | 49 | 1.05 | 1.09 | 20 % | 0.20 | 0.95 |
| low hotspot exposure | 23 | 1.15 | 1.17 | 24 % | 0.16 | 0.96 |
Route-level tests (permutation, medians of per-route |log ratio|):
- **Short vs long routes:** errors much larger on 1–5 km routes (distance 0.29 vs 0.11, p = 0.001; time 0.34 vs 0.17,
  p < 0.001); short routes are also **systematically too slow** (signed time 0.27 vs 0.06, p = 0.002).
  Route-level time error falls with length (Spearman −0.57).
- **Arterial vs sub-arterial:** all routes — distance 0.12 vs 0.29 (p = 0.004), time 0.17 vs 0.27 (p = 0.007), Jaccard
  0.20 vs 0.08 (p = 0.001). **Routes ≥ 5 km only** — distance p = 0.75, time p = 0.58 (no difference), but Jaccard 0.18 vs
  0.08 (p = 0.009) and recall 0.21 vs 0.10 (p = 0.017) remain. Within every length band, road overlap rises with the
  arterial share (Spearman 0.53 / 0.42 / 0.30). → The numeric gap is a **length effect**; the **road-knowledge gap is real**.
- **Hotspot exposure:** distance error higher on low-exposure routes (0.18 vs 0.11, p = 0.047); no time difference.

## 5. Naive baseline (plots r03, r10; `summary_baseline_speeds.csv`)
Baseline distance = straight line × 1.22 (median OSM detour, Phase 1); baseline speed = median Stage-2 speed near the slot
time (April scrape, other routes): 08:00 21.1 / 22.8 km/h (weekday / weekend), 14:00 19.0 / 18.6, 18:00 16.3 / 16.9,
23:00 25.0 / 24.4. The baseline is better at peak slots (LLM wins only 30 % at 08:00, 36 % at 18:00) and the LLM is better
at 14:00 (60 %) and on short (66 %) and sub-arterial (62 %) routes. **Caveat:** the baseline knows the exact coordinates;
the LLM gets only names.

## 6. Figures (`data/benchmark_v2/figures/phase4/`)
| Plot | Shows |
|---|---|
| r01_distance_scatter | LLM vs Google distance (log–log), by band |
| r02_time_scatter | LLM vs Google time (log–log), by slot — peak slots above the line, night below |
| r03_time_ratio_by_slot | time ratio per slot, LLM vs naive baseline |
| **r04_time_of_day_profile** | **headline:** LLM vs Google time-of-day profile |
| **r05_peak_night_ratio** | per-route peak/night ratio: LLM ~2× everywhere, Google 1.0–1.6 |
| r06_traffic_label_vs_index | traffic label vs Google traffic index |
| r07_error_by_group | abs. log error by band / road type / exposure |
| r08_road_validity_overlap | validity, recall, Jaccard by road type; Jaccard distribution |
| r09_consistency | spread over 3 samples |
| r10_llm_vs_baseline | LLM vs naive baseline error |
| r11_error_vs_arterial_share | route-level error vs arterial share |
