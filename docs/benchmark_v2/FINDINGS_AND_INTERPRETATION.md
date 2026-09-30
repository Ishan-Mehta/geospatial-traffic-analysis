# Findings and interpretation — Stage 6 v2 (status 2026-10-01)

*Can an LLM, using only its general knowledge, estimate routes, distances and travel times in Bangalore as well as
Google Maps?* This document summarises the study so far and what the results mean. Numbers: [PHASE4_RESULTS.md](PHASE4_RESULTS.md),
[PHASE2_RESULTS.md](PHASE2_RESULTS.md), [PHASE3_RESULTS.md](PHASE3_RESULTS.md). Caveats: [IMPORTANT_NOTES.md](IMPORTANT_NOTES.md).
Scope so far: **one model (gemini-3.8-flash), zero context, low thinking (condition A)**. Thinking (B), context (C) and
other models are not yet tested.

---
## 1. What was done
1. **Audit of v1** ([AUDIT_v1.md](AUDIT_v1.md)): the pilot compared the LLM on 14 tiny sensor legs (10 under 1.5 km) with
   ambiguous reverse-geocoded names; two "routes" were geocoding errors; only 1 of 22 LLM answers was saved. Unusable →
   rebuilt as v2; v1 becomes the pilot / lessons-learned section.
2. **Routes (Phase 1):** 70 well-known landmarks (metro stations, junctions, hospitals, tech parks, bus/rail stations …)
   → each **name looked up once** in Google Places (name → coordinate) with automatic checks and manual review →
   66 landmarks → **72 routes** (1.3–28.9 km on Google), balanced over length, road type and exposure to volatile roads.
   The LLM receives the landmark *name*; Google receives that landmark's *coordinate* — the same place by construction
   (Google's start/end points were within a median 10 m, max 83 m, of our coordinates).
3. **Ground truth (Phase 2):** Google Routes (`TRAFFIC_AWARE_OPTIMAL`, the Google Maps app's mode) for every route at
   08:00, 14:00, 18:00, 23:00 on each day of one future week (5–11 Oct 2026) = **2,016 queries** of *predicted typical
   traffic*. Google's route line was matched onto OpenStreetMap to obtain its road names.
4. **LLM (Phase 3):** the professor-approved zero-context prompt (origin, destination, city, weekday, time of day — with
   the clock time added) and a fixed JSON answer format (road list, km, minutes, traffic level, reasoning), sent to
   gemini-3.8-flash for the same 2,016 queries, plus repeats (10 routes × 3 answers) and a "where is this landmark?" check.
   Total cost **$1.83**.
5. **Comparison (Phase 4):** distance, time, time-of-day behaviour, traffic awareness, road names, consistency, and a
   naive formula baseline, broken down by route type (route-level bootstrap CIs, permutation tests).

---
## 2. Main findings
### F1 — The LLM knows the places and names real roads
All 64 landmarks were placed correctly (median 248 m from Google's point; none > 1.15 km). At least **95 %** of the
road names it gives are real Bangalore roads (a lower bound — some unmatched names are real but missing from our lists).
→ Unlike v1, errors are **not** caused by misidentified places, and outright hallucinated roads are rare.

### F2 — Distances are good; times are biased by time of day
- Distance: median **+6 %** vs Google (typical error 13 %) — the LLM has a reasonable sense of scale.
- Time: median **+12 %** (typical error 21 %), but this average hides a strong time-of-day bias:
  **+42 % at 08:00, +31 % at 18:00, −1 % at 14:00, −13 % at 23:00**; weekdays +17 %, weekends +2 %.

### F3 — Headline: the LLM knows *when* traffic is bad, but exaggerates it and applies it uniformly
- It orders times correctly: within a route its 28 times follow Google's order (median rank correlation **0.73**), and its
  traffic labels rise with Google's congestion (**ρ = 0.63**; "heavy" ≈ index 1.44, "light" ≈ 1.06).
- But it **exaggerates the rush-hour effect**: weekday peak ÷ night = **2.15** for the LLM vs **1.34** for Google (×1.6 too
  strong); it calls 92 % of weekday 08:00 trips "heavy" although Google's 08:00 is only mildly congested (Bangalore's
  morning peak comes later).
- It applies roughly the **same multiplier to every route**: per-route sensitivity does not correlate with Google's
  (ρ = **−0.24**). Within a time slot its labels barely track real congestion (14:00 ρ = 0.17, 23:00 ρ = 0.03).
- Interpretation: the model has learned a *city-level stereotype* ("rush hour ≈ double the time; night is free-flowing")
  rather than *route- and hour-specific* traffic knowledge.

### F4 — It does not know Google's route choice in detail
Only **22 %** of the roads on Google's route appear in the LLM's list (Jaccard 0.19); 57 % of the roads it names are on
Google's route. Its road lists also change between repeats (Jaccard 0.50 between samples) while its numbers barely move
(CV 3–4 %). → It knows the *main corridors*, not the *turn-by-turn path*.

### F5 — Short routes are hardest
1–5 km routes: typical time error 34 % (vs 17 % for 12–25 km) and **systematically too slow** (+27 % median). Route-level
time error falls with length (ρ = −0.57). Likely cause: fixed overheads (junction waits, "rush hour" padding) are added
regardless of distance, and small absolute errors are large relative errors on short trips.

### F6 — Arterial vs sub-arterial: road knowledge yes, numeric accuracy no (after controlling for length)
- Raw comparison: sub-arterial routes have larger distance/time errors (p < 0.01) — but half of them are short routes.
  Among routes ≥ 5 km there is **no** numeric difference (p = 0.75 / 0.58).
- Road knowledge does differ: overlap with Google's roads is half as large on sub-arterial routes even ≥ 5 km
  (Jaccard 0.08 vs 0.18, p = 0.009), and rises with the share of main roads within every length band.
- → The LLM "knows" the big named roads better, which is what online text is full of, but this matters for *which roads*
  more than for *how long*.

### F7 — A trivial formula is about as good
Straight-line distance × 1.22 at a typical Stage-2 speed per time slot beats the LLM on median error (time 0.17 vs 0.21
abs. log ratio; distance 0.10 vs 0.13) and wins at peak slots; the LLM wins at 14:00, on short and on sub-arterial routes.
Caveat: the formula uses exact coordinates, the LLM only names — but it shows the LLM's numbers add little beyond a
distance-and-average-speed rule of thumb.

### F8 — Stable answers, no drift
Same model version for all 2,640 calls; repeat answers vary by 3–4 %; same traffic label 96 % of the time.

---
## 3. Against the midsem hypotheses
| Hypothesis (midsem §3.4.3) | Verdict so far | Evidence |
|---|---|---|
| H1: better on major arterial roads, worse on sub-arterial / internal roads | **Partly supported** — for *road knowledge* (overlap, recall), not for distance/time once route length is controlled | F4, F6 |
| H2: poor time estimation (no real-time data) | **Supported, with nuance** — time errors are larger than distance errors and strongly biased by time of day, but the LLM does know *relative* timing | F2, F3, F7 |
| H3: well-structured context (adjacency lists, distance tables) improves pathfinding | **Not yet tested** (condition C) | — |
| H4: India-specific models/APIs may do better | **Not tested** | — |
Additional finding for the report: **the shortest path and the fastest path use different road classes in Bangalore**
(Google's fastest routes run mostly on arterials; median arterial share 0.65 vs 0.50 on the shortest paths; PHASE2_RESULTS §3).

---
## 4. Limitations (state these in the report)
1. **One model, one prompt style, low thinking.** Results describe gemini-3.8-flash under zero context; thinking (B),
   context (C) and other LLMs may differ.
2. **Ground truth is Google's *predicted* traffic** for one week (5–11 Oct 2026, incl. the Sat 10 Oct holiday), not live
   traffic; Google itself is a model.
3. **Time-slot labels:** "Morning Rush (08:00)" may prime the LLM towards rush-hour estimates; the clock time was added to
   reduce this, but the label remains (professor's prompt).
4. **Road-name matching is fuzzy**; the reference lists are incomplete (validity is a lower bound); road lists vary between
   samples, so single-answer overlap scores are noisy.
5. **Group sizes:** only 12 sub-arterial routes (Google's fastest routes are mostly arterial; routes were selected on
   shortest-path estimates) — group results are indicative; continuous and length-controlled analyses are more reliable.
6. **The naive baseline has an information advantage** (exact coordinates) and uses Stage-2 speeds from other routes in April.
7. `staticDuration` is not free-flow time (historical traffic ETA) — traffic is measured with the traffic index instead.

---
## 5. What would strengthen the study next (for discussion)
1. **Condition B (high thinking)** on the same 2,016 queries (≈ $8.5): does reasoning reduce the rush-hour exaggeration?
2. **Condition C (context):** give the LLM a road list / adjacency / typical speeds by hour — the midsem's core question.
3. **Another model family** (GPT / Claude) with the same prompts — is the stereotype Gemini-specific?
4. **More sub-arterial routes** (Q13 option C) if the arterial vs sub-arterial comparison is a headline.
5. Report-ready charts and the v1 pilot section (Phase 5).
