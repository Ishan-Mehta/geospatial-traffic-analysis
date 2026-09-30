# Discussion points for the professor — Stage 6 v2 (LLM vs Google Maps routing)

Prepared 2026-10-01. Part A = the questions (one line each). Part B = context and details per question.
Supporting docs: [PHASE1_RESULTS.md](PHASE1_RESULTS.md) (route list), [IO_SPEC.md](IO_SPEC.md) (exact prompts/payloads),
[AUDIT_v1.md](AUDIT_v1.md) (why v1 was redone), [IMPORTANT_NOTES.md](IMPORTANT_NOTES.md) (caveats).

---
## Part A — Summary and questions

**Where we are:** the v1 pilot was audited and found unusable (tiny sensor legs, ambiguous names, 1 of 22 LLM answers
actually saved). v2 is rebuilt: **72 routes between 66 verified landmarks**, balanced over distance, road type and
exposure to volatile roads; each route asked **28 times** (Mon–Sun × 4 times of day) to **Google (predicted traffic)**
and to **Gemini** with the same origin/destination. All code is built and tested offline; no benchmark API calls yet.

| # | Question | Needs |
|---|---|---|
| Q1 | Is the **72-route list** (landmark-to-landmark, 1–25 km, 18 balanced groups) acceptable? | approval / changes |
| Q2 | OK to append the **clock time** to the time-of-day label, e.g. "Evening Rush (18:00)"? | approval (prompt change) |
| Q3 | OK to add a **one-line description per JSON field** (same field names; road names only; time incl. traffic)? | approval (schema change) |
| Q4 | Is **Google's predicted traffic** for a fixed future week (5–11 Oct 2026) acceptable as ground truth, instead of live traffic? | approval |
| Q5 | **Models:** gemini-3.8-flash (main) + gemini-2.5-flash (cheap comparison); later GPT / Claude? | approval / priorities |
| Q6 | **Thinking:** A = lowest thinking (Gemini 3.x cannot fully disable it), B = high thinking. Acceptable framing? | approval |
| Q7 | Keep the optional **grounding check** ("where is this landmark?") to separate "unknown place" from "bad routing"? | yes / no |
| Q8 | **Data use:** Google terms restrict sharing raw Google data — may the repo be public? what can we publish? | guidance |
| Q9 | Agree with the **metrics** and the headline metric (time-of-day sensitivity)? | approval |
| Q10 | **Next scope** after the baseline: context ablation (condition C), other LLMs, MapmyIndia — which first? | priorities |
| Q11 | Present v1 as a **"pilot / lessons learned"** section? | yes / no |
| Q12 | **Budget** ≈ $6 without thinking, ≈ $30 with thinking — OK? | approval |

**Time constraint:** for the week 5–11 Oct, all Google queries must be sent **before Mon 5 Oct, 07:30 IST**. If Q1/Q4
cannot be settled by then, the reference week moves to 26 Oct–1 Nov (no other impact).

---
## Part B — Details

### Q1. The route list
- **Why new routes:** v1 used Stage-4 "legs" (sensor segments between waypoints), 10 of 14 under 1.5 km, with names
  produced by reverse geocoding ("Start of X → End of X", a destination literally called "4) (Kengeri)"). Two long v1 routes
  came from mis-geocoded waypoints (a 7 km road became a 30 km leg).
- **How v2 routes were made:** 70 landmarks drafted (metro stations, junctions, hospitals, tech parks, bus/rail stations,
  malls, campuses) → each **name looked up once** with Google Places (name → coordinate) → automatic checks (name match,
  area match, ambiguity, not an area, within 150 m of a road) → manual review: 19 flagged approved, 4 dropped, 1 replaced →
  **66 landmarks**. All pairs 0.7–22 km apart → OSM shortest path → tags → balanced selection.
- **Groups (18):** distance band (1–5 / 5–12 / 12–25 km) × road type by share on arterial roads (arterial / mixed /
  sub-arterial, from OSM road classes) × hotspot exposure (high / low share of the route on the most volatile Stage-4 legs).
  4 routes per group = 72 routes; route length 1.3–23.9 km (median 9.7).
- The LLM receives only the landmark **name**; Google receives that landmark's coordinate — same place by construction.
- **Ask:** approve the list, or name landmarks/areas to add or remove. Full table: PHASE1_RESULTS.md §5.

### Q2. Clock time in the prompt
- v1 prompt: `Time of day: Evening Rush`. Google, however, is asked for an exact departure time (18:00). The LLM might
  picture 17:00 or 19:30 — the time comparison would then partly measure the label's vagueness.
- Proposed: `Time of day: Evening Rush (18:00)` (also Morning Rush (08:00), Off-Peak (14:00), Night (23:00)).
  Everything else in the prompt is unchanged. Approved by Ishan; needs your OK because it changes the approved prompt.

### Q3. Field descriptions in the JSON schema
- The schema forces the LLM's answer into 5 fields (route list, distance km, time minutes, traffic level, reasoning) — this
  already makes answers machine-readable. But "suggested_route" was undefined, so models mix roads, landmarks and
  abbreviations, and "time" did not say whether traffic is included.
- Proposed: keep field names, types and the traffic enum; add one-line descriptions ("ordered list of road names driven,
  road names only"; "driving time … including expected traffic"; …). Exact text: IO_SPEC.md §4.
- Not added (to keep the task simple): a separate "time without traffic" field — possible later ablation.

### Q4. Ground truth = Google's predicted traffic
- Each query uses a **future** departure time in one fixed week, so Google returns its **predicted typical** travel time
  (historical patterns + expected conditions), with the most exhaustive routing mode (`TRAFFIC_AWARE_OPTIMAL`, the mode used
  by the Google Maps app). Live traffic would need 2,016 queries at the exact slot times over a real week.
- Week: **Mon 5 – Sun 11 Oct 2026**. Sat 10 Oct is a public holiday (Mahalaya Amavasya): kept, tagged, and weekend
  results reported with and without it (the LLM is only told "Saturday"). Navaratri begins Sun 11 Oct (not tagged, kept
  as a normal weekend day).
- Google also returns the **no-traffic** time (staticDuration) and the route geometry; the geometry is matched to OSM to
  get the ordered road names used to score the LLM's road list.

### Q5. Models
- **gemini-3.8-flash** (newest Flash; $0.75 / $3.75 per 1M tokens until 31 Dec 2026, then doubles) as the main model.
- **gemini-2.5-flash** (older generation, $0.30 / $2.50) as a cheap comparison — also the only one where thinking can be
  switched fully off. (Availability for our key to be confirmed by the first test call.)
- The code is provider-agnostic: GPT or Claude can be added with one adapter + one config entry, same prompts.
- Each call is independent (no memory between queries); queries are sent in a shuffled order; the exact model version is
  logged on every answer.

### Q6. Thinking conditions
- Condition A = lowest thinking level the model allows (gemini-3.8-flash: "LOW"; gemini-2.5-flash: off). Condition B =
  high thinking. Gemini 3.x cannot disable thinking entirely, so A is "minimal reasoning", not "no reasoning"; the number of
  thinking tokens is logged per answer and will be reported.
- B is the costliest part and runs last.

### Q7. Grounding check (optional)
- Separate from the benchmark prompts: once per landmark, the LLM is asked "Where exactly is <landmark>?" (area +
  coordinates). Its answer is compared with the Google coordinate (the answer key).
- If the LLM pictures a different place (as in v1, where "Vishveshwaraya Nagar" was read as the wrong part of the city),
  its route error is a *place-identification* error, not a *routing* error. Routes with such landmarks are **flagged,
  not removed**, and reported separately.
- Flag rule: coordinates > 2 km off **and** the area name not matching Google's address (LLMs are imprecise with raw
  coordinates even for places they know). Cost ≈ 64 calls, < $0.10.

### Q8. Data use and publication
- Google Maps Platform terms restrict caching, storing and redistributing Google content (routes, place results,
  coordinates). We keep it locally for analysis only and no longer commit it to git.
- The GitHub repo is currently **public**. Earlier Stage-1 commits already published Google-geocoded coordinates
  (`data/processed/geocoded_*.csv`) and one sample Google response (`data/sample_response.json`).
- **Ask:** may the repo stay public (with Google data removed), or should it be private? For the report/paper we plan to
  publish derived results (errors, correlations, aggregated maps) and landmark names — not raw Google responses.

### Q9. Metrics (Phase 4)
Per query, LLM vs Google for the same route/day/time:
- **Distance and time:** log-ratio ln(LLM/Google), absolute error, over/under-estimation; medians (not means).
- **Time-of-day sensitivity (proposed headline):** does the LLM's peak/night time ratio track Google's for each route?
- **Traffic awareness:** rank correlation between the LLM's traffic label and Google's congestion ratio.
- **Road validity:** share of the LLM's road names that exist in Bangalore's OSM street list (hallucination check).
- **Road overlap:** Jaccard similarity between the LLM's roads and the roads on Google's route.
- **Consistency:** spread over 3 samples on 10 routes. **Naive baseline:** straight-line distance × 1.22 detour at a
  typical speed per time slot — does the LLM beat a trivial formula?
- Broken down by distance band, road type, hotspot exposure, time slot and day type; compared one factor at a time
  (24–36 routes per level) because 4 routes per group are too few for cell-level claims.
- Hypotheses from the midsem: better on arterial than sub-arterial roads; poor time estimation; context helps (Q10).

### Q10. Next scope
- **Condition C — context ablation** (the midsem's core question): give the LLM road lists / adjacency / congestion
  tables and measure the improvement. Not built yet.
- **Other LLMs** (GPT, Claude): adapters ready as stubs.
- **MapmyIndia** as a second ground truth (midsem plan). **OSM-Dijkstra** on the Stage-2 speeds as a transparent ground truth.
- **Ask:** order of priority.

### Q11. v1 as a pilot
- v1 results are not comparable (different routes, names, prompt details) and only 1 LLM answer was valid. Proposed: a
  short "pilot / lessons learned" section citing the audit findings (AUDIT_v1.md).

### Q12. Budget
| Step | Calls | ≈ Cost |
|---|---|---|
| Google (predicted traffic) | 2,016 | $0 (within 5,000 free / month) |
| Gemini grounding | 64 | < $0.10 |
| gemini-3.8-flash, condition A (+ consistency subset) | 2,576 | ≈ $3.8 |
| gemini-2.5-flash, condition A | 2,016 | ≈ $1.9 |
| gemini-3.8-flash, condition B (thinking) | 2,016 | ≈ $19 (thinking tokens uncertain) |
| **Total** | | **≈ $6 without B · ≈ $25 with B** |
