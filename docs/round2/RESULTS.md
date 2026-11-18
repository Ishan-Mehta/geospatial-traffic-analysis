# Round 2 results — Google Maps vs Gemini (neutral prompt), 18 Nov 2026

For the report. ChatGPT is not included yet (no API access). Plan and settings: `ROUND2_PLAN.md`; runs: RUN_LOG
R-46…R-49; decisions: D-66…D-70. Raw data is git-ignored in `data/benchmark_round2/`; aggregate tables in
`data/benchmark_round2/results/summary_*.csv`. Figures: `docs/round2/figures/` (same layout as the Round 1 report figures).

## 1. What was collected
| Source | What | Count | Notes |
|---|---|---|---|
| Google Maps | Predicted traffic (`TRAFFIC_AWARE_OPTIMAL`), week **Sat 28 Nov – Fri 4 Dec 2026**, 08:00 / 14:00 / 18:00 / 23:00 | 2,016 whole routes + 2,016 sub-route sets | 0 failed; endpoints 100 % within tolerance; 37 of 72 routes used more than one path during the week; no public holiday in the week |
| Google sub-routes | Second request with a stop at each road change (40 m past it, 150 m on one retry) | 1,953 requests + 28 retries; 58 single-road queries | Sub-route legs add up to the whole route within 2 % (distance) for every query; time within 10 % for all but 5 |
| Gemini | `gemini-3.8-flash`, lowest thinking, temperature 1.0, neutral prompt, road-by-road answer format | 2,016 main + 560 repeats | All valid, one model version, $3.62 |
| Gemini format control | Neutral prompt, whole-route format (no road-by-road breakdown), 10 routes × 28 | 280 | $0.21 |

Neutral prompt = Round 1 instructions without "Bangalore has heavy peak-hour traffic", with "Consider the time of day
and day of week when estimating travel time." kept; the question gives only the clock time ("Time of day: 08:00");
no example road names. Exact text and request bodies: `ROUND2_PLAN.md` §3–4.

## 2. Headline numbers (one answer per query, 2,016 queries; Round 1 = old prompt, October week)
| Measure | Round 1 | Round 2 |
|---|---|---|
| Distance, Gemini ÷ Google (median) | 1.06 | 1.08 |
| Distance, typical miss | 13 % | 14 % |
| Distance within 10 % of Google | 40 % | 35 % |
| Time, Gemini ÷ Google (median) | 1.12 | **1.01** |
| Time, typical miss | 21 % | **23 %** |
| Time within 10 % of Google | 23 % | 23 % |
| Typical absolute miss | 5.8 min, 1.1 km | 6.1 min, 1.3 km |
| Weekday time ratio 08:00 / 14:00 / 18:00 / 23:00 | 1.49 / 1.01 / 1.36 / 0.88 | **1.29** / 0.98 / 1.32 / **0.75** |
| Rush-hour ÷ night per route (median), Gemini vs Google | 2.15 vs 1.34 | **2.40** vs 1.34 |
| Routes where Gemini's rush-hour increase exceeds Google's | 72 / 72 | 72 / 72 |
| Order of a route's 28 times (within-route rank correlation) | 0.73 | 0.81 |
| Traffic label vs Google traffic index (rank correlation) | 0.63 | 0.73 |
| Overlap with Google's roads (Jaccard / share of Google's roads named) | 0.19 / 22 % | 0.17 / 20 % |
| Road names found in the reference lists (lower bound) | 95 % | 96 % |
| Simple formula (straight line × 1.22 at typical speed): typical time / distance error vs Gemini | 0.17 vs 0.21 / 0.10 vs 0.13 | 0.17 vs 0.23 / 0.10 vs 0.14 |
| Repeats: spread of distance / time (CV), same label | 2.7 % / 3.8 %, 96 % | 3.9 % / 5.8 %, 93 % |

The overall time ratio of 1.01 looks "accurate" only because rush-hour overestimates and night underestimates cancel.
The typical miss (23 %) did not improve.

## 3. Time of day (figures B, C, D, F)
- **The rush-hour stereotype remains, and is stronger.** Weekday time relative to the same trip at night: Gemini 2.03 / 1.68 / **2.75** / 1.00 at 08/14/18/23 h vs Google 1.13 / 1.25 / 1.52 / 1.00. Night is now 25 % too fast (Round 1: 12 %).
- **Labels are still set by the clock.** Weekdays: 08:00 heavy 56 % / moderate 44 %; 14:00 moderate 100 %; 18:00 heavy 100 %; 23:00 light 100 %. 08:00 "heavy" fell from 92 % (Round 1) to 56 %.
- Short trips still get the largest multiplier (1–5 km: Gemini 2.61 vs Google 1.24); the Yeshwanthpur Metro → Peenya Metro exception (Google predicts night slower than 08:00) appears again in the new week.
- Google's own pattern is almost identical to October (weekday traffic index 1.19 / 1.35 / 1.63 / 1.05).

## 4. Effect of the prompt wording (old vs neutral; Gemini only, same questions)
On the 10 repeat routes, weekdays, three versions of the same 280 questions:
| | Old prompt (Round 1) | Neutral, whole-route format | Neutral, road-by-road format |
|---|---|---|---|
| 08:00 called "heavy" | 98 % | 60 % | 60 % |
| 08:00 typical time | 45 min | 39 min | 39 min |
| 18:00 called "heavy" | 100 % | 100 % | 100 % |
| 23:00 typical time | 22 min | 22 min | 20 min |
| Rush-hour ÷ night (median per route) | 2.07 | 1.96 | 2.37 |
| Time vs Round 1, same query (median) | — | 1.00 | 0.91 |
Reading: the old wording ("Morning Rush", "heavy peak-hour traffic") mainly inflated **08:00** (labels and ~13 % longer times).
It did not create the overall stereotype: with neutral wording, rush hour is still about double the night time and
labels still follow the clock. Asking for a road-by-road breakdown shortens night trips and raises the rush-hour ratio.
Distances barely change between versions (10.5 / 11.0 / 10.75 km median).

## 5. Sub-routes (Gemini road-by-road vs Google sub-routes; `summary_subroutes.csv`, script `7_subroutes_r2.py`)
- Google: median 6 sub-routes per query; Gemini: median 4 roads.
- Gemini's road-by-road distances and times **add up exactly to its own totals** in every answer.
- Name pairing (same fuzzy rule as before): 90 % of queries have at least one paired road; 1.7 paired roads per query; the pairs cover a median **37 %** of Google's route length.
- Paired roads: distance ratio 1.20, typical miss **48 %**; time ratio 1.21, typical miss **47 %** — far worse than the whole route (14 % / 23 %). Errors on individual roads cancel out in the totals.
- Paired-road time ratio by slot: 08:00 1.28, 14:00 1.13, 18:00 1.49, 23:00 0.89 — the same time-of-day pattern at road level.
- Caveats: pairing depends on names (Google uses e.g. "NH 44" where others say "Outer Ring Road"); generic names such as "Service Rd" can pair loosely; Google's leg distances are shifted by the stop offset (exact per-road distances come from the steps and are used for distance).

## 6. Where Gemini does worst (figure H; `summary_group_tests.csv`, `summary_length_controlled.csv`)
- Length still matters most: typical time miss 43 % (1–5 km) vs 27 % (5–12 km) vs 22 % (12–29 km); distance 31 % / 14 % / 12 %; short vs long p = 0.0002 for both.
- Short trips are **no longer systematically too slow** (signed bias p = 0.44; Round 1 p = 0.002). The old rush-hour wording was likely behind that.
- Main vs smaller roads, trips ≥ 5 km (37 vs 6 routes): distance miss **11 % vs 23 % (p = 0.006)**, time no difference (p = 0.73), road overlap 0.16 vs 0.09 (p = 0.06). This differs from Round 1, where distance showed no difference and overlap did; with only 6 such routes, treat both rounds as indicative.

## 7. Other observations
- Only 38 % of Round 2 times are multiples of 5 min (Round 1: 72 %): totals built from road-by-road parts are less "round".
- Thinking tokens were reported for 489 of 2,016 answers (Round 1: 28), still at the lowest setting.
- Repeats vary slightly more than in Round 1 (time CV 5.8 % vs 3.8 %; identical road list less often).

## 8. Limitations to state
One LLM so far (ChatGPT pending); Google is predicted traffic for one week; the two rounds use different Google weeks
(Gemini questions contain no date, so the LLM comparison between rounds is direct); sub-route pairing is name-based and
partial; 12 sub-arterial routes only; the formula baseline knows exact coordinates.
