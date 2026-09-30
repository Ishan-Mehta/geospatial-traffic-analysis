# Phase 3 results — LLM queries, condition A (2026-10-01)

**Status:** grounding + condition A (main + consistency) complete for **gemini-3.8-flash**. Condition B: 1 test call only
(locked, D-46). Data (local only, git-ignored, D-43): `data/benchmark_v2/llm/`. Runs R-30…R-37 in [RUN_LOG.md](RUN_LOG.md).
Exact prompts/settings: [IO_SPEC.md](IO_SPEC.md).

## 1. Runs
| Run | Calls | Result | Time |
|---|---|---|---|
| Grounding ("where is <landmark>?") | 64 | 64 OK | ~1 min |
| Condition A, main (72 routes × 28 queries) | 2,016 | 2,016 OK, 0 retries | 03:06–03:59 IST |
| Condition A, consistency (10 routes × 28 × 2 extra) | 560 | 560 OK | 04:00–04:11 IST |
| Condition B | 1 (test) | OK, 918 thought tokens | — |
All answers: model version `gemini-3.8-flash` (no change mid-run), temperature 1.0, thinking `LOW`; 0 invalid numbers;
0 duplicates. Thought tokens were reported on only 31 of 2,576 condition-A answers (median 133 when present).
Traffic labels used: heavy 993 · moderate 816 · light 760 · none 7.

## 2. Cost (from logged token counts; gemini-3.8-flash $0.75 / $3.75 per 1M tokens)
Condition A $1.81 · grounding $0.02 · B test $0.004 · **total $1.83 (≈ ₹161, before GST)**. Prepay loaded ₹700.
(v2 also used 1 Gemini call rejected on postpay and 1 rejected gemini-2.5-flash call — no charge.)

## 3. Grounding — the LLM knows every landmark
LLM coordinate vs Google coordinate: median **248 m**, 90th percentile 0.86 km, max 1.15 km; **0 landmarks misplaced**
(rule: > 2 km and locality mismatch); 56/64 localities match Google's address. → Route errors in this benchmark are
**not** place-identification errors (unlike v1).

## 4. Consistency (280 queries answered 3 times)
Median coefficient of variation: distance **2.7 %**, time **3.8 %**; same traffic label in 96 %; identical time in 45 %;
**identical road list in only 6 %** (wording/order/extra roads vary) → road-overlap metrics need name normalisation and
should be read with this run-to-run variation in mind.

## 5. Preliminary comparison with Google (first look, not the Phase-4 analysis)
Condition A, sample 0, 2,016 queries joined on (route, day, slot):
| Measure | Result |
|---|---|
| Distance LLM ÷ Google | median **1.06** (IQR 0.98–1.18) |
| Time LLM ÷ Google | median **1.12** (IQR 0.90–1.40) |
| Time ratio by slot | 08:00 **1.42** · 14:00 0.98 · 18:00 **1.31** · 23:00 **0.87** |
| Weekday peak ÷ night time (per route, median) | LLM **2.15** vs Google 1.33 |
| Spearman (LLM traffic label, Google traffic index) | **0.63** |
| Distance ratio by road type | arterial 1.05 · mixed 1.07 · sub-arterial **1.15** |
Reading (to be confirmed): the LLM knows *when* traffic is worse but **exaggerates the time-of-day effect** (too slow at
peaks, too fast at night); distances are close, less so on sub-arterial routes (midsem hypothesis 1).
