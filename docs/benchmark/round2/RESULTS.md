# Round 2 results — Google Maps vs Gemini vs ChatGPT (neutral prompt)

Prompts and requests: [PROMPTS_AND_REQUESTS.md](PROMPTS_AND_REQUESTS.md). Raw Google and LLM data is not published;
aggregate tables are in `data/benchmark_round2/results/` (one folder per model, plus `summary_models*.csv` for the
side-by-side comparison) and figures in [figures/](figures/). Numbers use one answer per query (2,016 queries) unless
stated. "Typical miss" = median absolute percentage error; "ratio" = LLM ÷ Google (1.00 = equal).

## 1. Data collected
| Source | Setting | Collected | Notes |
|---|---|---|---|
| Google Maps | Predicted traffic (`TRAFFIC_AWARE_OPTIMAL`), Sat 28 Nov – Fri 4 Dec 2026, 08:00 / 14:00 / 18:00 / 23:00 | 2,016 whole routes + 2,016 sub-route sets | No failures; endpoints within tolerance for 100 %; 37 of 72 routes used more than one path in the week; no public holiday |
| Google sub-routes | Second request with a stop 40 m past each road change (150 m on one retry) | 1,953 requests + 28 retries (58 single-road queries need none) | Legs add up to the whole-route distance within 2 % for every query; time within 10 % for all but 5 |
| Gemini | `gemini-3.8-flash`, lowest thinking level, temperature 1.0 | 2,016 + 560 repeats + 280 format control | All valid; $3.83 |
| ChatGPT | `gpt-5.4-mini-2026-03-17`, reasoning effort none, temperature 1.0 | 2,016 + 560 repeats + 280 format control + 64 landmark checks | All valid; $3.33 |

Both LLMs got byte-identical instructions, questions and answer format, no tools, one request per query. The questions
contain no date (only weekday and clock time), so the LLM answers do not depend on when they were collected.

## 2. Headline comparison (`summary_models.csv`; Round 1 = Gemini with the original prompt, October)
| Measure | Gemini, Round 1 | Gemini | ChatGPT |
|---|---|---|---|
| Distance ratio (median, 95 % CI) | 1.06 | 1.08 (1.05–1.13) | **1.25** (1.18–1.34) |
| Distance typical miss | 13 % | **14 %** | 31 % |
| Distance within 10 % of Google | 40 % | 35 % | 19 % |
| Time ratio (median, 95 % CI) | 1.12 | 1.01 (0.97–1.05) | **1.27** (1.20–1.37) |
| Time typical miss | 21 % | **23 %** | 32 % |
| Time within 10 % of Google | 23 % | 23 % | 18 % |
| Typical absolute miss | 5.8 min, 1.1 km | 6.1 min, 1.3 km | 8.8 min, 2.7 km |
| Answers longer / slower than Google | 69 % / 63 % | 67 % / 51 % | 76 % / 74 % |
| Rush hour ÷ night per route (Google 1.34) | 2.15 | **2.40** | 1.84 |
| Routes where the LLM's rush-hour increase exceeds Google's | 72 / 72 | 72 / 72 | 71 / 72 |
| Order of a route's 28 times (within-route rank correlation) | 0.73 | 0.81 | 0.62 |
| Traffic label vs Google traffic index (rank correlation) | 0.63 | 0.73 | 0.63 |
| Road names found in reference lists (lower bound) | 95 % | 96 % | 91 % |
| Share of Google's roads named / overlap (Jaccard) | 22 % / 0.19 | 20 % / 0.17 | 14 % / 0.12 |
| Repeats: time spread (CV) / same label | 3.8 % / 96 % | 5.8 % / 93 % | 11.7 % / 91 % |
| Landmarks: median location error / misplaced | 248 m / 0 | (Round 1 check reused) | 645 m / 1 |
| Simple formula beats the LLM on time (share of queries) | 56 % | 57 % | 65 % |

**Gemini vs ChatGPT on the same 72 routes** (`summary_models_paired_tests.csv`; per-route median |log ratio|, two-sided
sign-flip permutation test, 10,000 shuffles): Gemini is more accurate on distance for **78 %** of routes (0.13 vs 0.28)
and on time for **63 %** (0.22 vs 0.30); p < 0.0001 for both.

## 3. Time of day (figures M1, M2; per model: B, C, D, F)
Weekday time relative to the same trip at 23:00 (median):
| | 08:00 | 14:00 | 18:00 | 23:00 |
|---|---|---|---|---|
| Google | 1.13 | 1.25 | 1.52 | 1.00 |
| Gemini | 2.03 | 1.68 | **2.75** | 1.00 |
| ChatGPT | 1.73 | 1.40 | 1.91 | 0.99 |

Weekday time ratio vs Google by slot: Gemini 1.29 / 0.98 / 1.32 / **0.75**; ChatGPT **1.59** / 1.20 / 1.38 / 1.07.
- **Both exaggerate rush hour on (almost) every route**, Gemini more strongly. Gemini is too slow at the peaks and too
  fast at night (errors partly cancel); ChatGPT is too slow at every hour, most at 08:00.
- **Both label traffic by the clock**, not by the route. Weekdays: Gemini 08:00 heavy 56 %, 14:00 moderate 100 %,
  18:00 heavy 100 %, 23:00 light 100 %; ChatGPT 08:00 heavy 80 %, 14:00 moderate 91 %, 18:00 heavy 95 %, 23:00 light 100 %.
- Short trips get Gemini's largest rush-hour multiplier (1–5 km: 2.61 vs Google 1.24); ChatGPT's multiplier is about
  the same for all lengths (1.81–1.87). Neither follows Google's route-to-route differences.
- Yeshwanthpur Metro → Peenya Metro: Google again predicts night slower than 08:00; both LLMs predict the usual pattern.

## 4. Effect of the prompt wording (`8_prompt_effect.py`, figure I)
Gemini on the 10 repeat routes, weekdays, three versions of the same 280 questions:
| | Original prompt (Round 1) | Neutral, whole-route answer | Neutral, road-by-road answer |
|---|---|---|---|
| 08:00 labelled "heavy" | 98 % | 60 % | 60 % |
| 08:00 typical time | 45 min | 39 min | 39 min |
| 18:00 labelled "heavy" | 100 % | 100 % | 100 % |
| 23:00 typical time | 22 min | 22 min | 20 min |
| Rush hour ÷ night | 2.07 | 1.96 | 2.37 |
- The original wording ("Morning Rush", "Bangalore has heavy peak-hour traffic") mainly inflated **08:00**. Removing it
  did not remove the rush-hour stereotype.
- Asking for a road-by-road answer changes the totals: Gemini's night trips get shorter and its rush-hour ratio rises;
  ChatGPT's times rise at every hour (10 repeat routes: 08:00 40 → 50.5 min, 23:00 25 → 30.5 min; rush hour ÷ night
  1.60 → 1.79) and its distances grow (median 11.5 → 13.0 km). ChatGPT has no original-prompt data.

## 5. Sub-routes (Google stopover legs vs the LLM's road-by-road answer; `7_subroutes_r2.py`)
| | Gemini | ChatGPT |
|---|---|---|
| Roads per answer (Google sub-routes: 6) | 4 | 4 |
| Answers whose road-by-road parts add up to the totals (within 5 %) | all | all but 7 |
| Queries with at least one road paired by name | 90 % | 73 % |
| Share of Google's route length covered by paired roads | 37 % | 18 % |
| Paired roads: distance ratio / typical miss | 1.20 / 48 % | 1.74 / 76 % |
| Paired roads: time ratio / typical miss | 1.21 / 47 % | 1.75 / 77 % |
| Paired-road time ratio 08 / 14 / 18 / 23 h | 1.28 / 1.13 / 1.49 / 0.89 | 2.15 / 1.76 / 1.84 / 1.46 |
Per-road estimates are much less accurate than the totals; errors on individual roads cancel out in the whole route.
Pairing depends on road names (e.g. Google "NH 44" vs "Outer Ring Road"), so coverage is partial.

## 6. Where the LLMs do worst (figure H; `summary_group_tests.csv`, `summary_length_controlled.csv`)
| Typical miss by trip length | 1–5 km | 5–12 km | 12–29 km |
|---|---|---|---|
| Gemini distance / time | 30 % / 33 % | 13 % / 23 % | 10 % / 20 % |
| ChatGPT distance / time | 50 % / 46 % | 29 % / 36 % | 24 % / 25 % |
- Short vs long routes: errors clearly larger on short routes for both (Gemini p = 0.0002; ChatGPT distance p = 0.009,
  time p = 0.0004). ChatGPT's distance overestimate is largest on short routes (median ratio 1.35 for 1–5 km).
- Main vs smaller roads on trips of 5 km or more (37 vs 6 routes): Gemini distance miss 11 % vs 23 % (p = 0.006), time
  no difference; ChatGPT no clear difference in either (p ≥ 0.44). Overlap with Google's roads is lower on
  smaller-road routes for both (borderline, p ≈ 0.05–0.10). Only 12 smaller-road routes: indicative.

## 7. Landmark knowledge (ChatGPT; Gemini from Round 1)
ChatGPT: median 645 m from Google's point (Gemini: 248 m); 9 landmarks more than 2 km off, 1 misplaced (Silk Institute
Metro Station, 6.0 km); next largest: Whitefield (Kadugodi) Metro 5.9 km, Sony World Junction 2.7 km. One route has a
misplaced endpoint (flagged, not removed). Locality names match Google's address for 60 of 64.

## 8. Other observations
- Round numbers: 38 % (Gemini) and 29 % (ChatGPT) of times are multiples of 5 min (Round 1 Gemini: 72 %); totals built
  from road-by-road parts are less round.
- ChatGPT used no reasoning tokens; Gemini reported a median of ~140 thinking tokens at its lowest setting.
- ChatGPT's repeated answers vary twice as much as Gemini's (time CV 11.7 % vs 5.8 %).

## 9. Limitations
Two LLMs, one prompt style, lowest reasoning settings; Google is predicted traffic for one week (Round 1 and Round 2
use different weeks; the LLM questions contain no date); sub-route pairing is name-based and partial; 12 smaller-road
routes; the formula baseline knows exact coordinates; ChatGPT has no original-prompt round.

## 10. Figures
| Figure | File |
|---|---|
| M1 — weekday time ÷ Google by slot, per model | `figures/fig_M1_time_by_slot_models.png` |
| M2 — shape of the day: Google, Gemini, ChatGPT | `figures/fig_M2_day_shape_models.png` |
| A–H — per model (routes map, time by slot, day shape, rush-hour multiplier, scatter, labels, Google heatmap, where worst) | `figures/<model>/fig_A … fig_H` |
| I — prompt and format effect | `figures/<model>/fig_I_prompt_effect.png` |
Model folders: `gemini_38_flash`, `openai_main` (ChatGPT). Diagnostic plots: `data/benchmark_round2/figures/`.
