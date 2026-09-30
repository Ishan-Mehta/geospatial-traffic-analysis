# Code guide — Phase 2 (Google ground truth) and Phase 3 (LLM queries)

Written 2026-10-01 for Ishan's review; updated the same day after Ishan's decisions (D-26/27/28/35/36). Exact prompts and payloads: [IO_SPEC.md](IO_SPEC.md). **No real API call has been made by any of this code.**
Everything below was tested offline with `--mock`, fake HTTP/SDK objects, and `--dry-run`.
Definitions: [METHODOLOGY.md](METHODOLOGY.md) §5–6 · decisions: D-26…D-34 in [DECISIONS.md](DECISIONS.md).

## 1. Files
| File (in `src/llm_benchmark/`) | Role | Network? |
|---|---|---|
| `v2_common.py` | Shared helpers: distance, fuzzy names, JSONL read/append, API-error translation, fatal-error detection, OSM network (snapping, **map-matching**), tag functions | none |
| `4_query_gmaps_v2.py` | Phase 2: Google Routes, 28 queries per route | **paid** (except `--dry-run`, `--status`, `--mock`) |
| `4b_process_gmaps_v2.py` | Phase 2: offline analysis of Google answers → final tags, plots | none |
| `llm_clients.py` | Phase 3: one `call_llm()` for every provider (Gemini real; mock; OpenAI/Anthropic stubs) | Gemini adapter is **paid** |
| `3_query_llm_v2.py` | Phase 3: consistency subset, grounding check, benchmark conditions A/B | **paid** (except `--dry-run`, `status`, `select-consistency`, `grounding-eval`, `--mock`) |
| `prompts/grounding_system_prompt.txt` | New system prompt for the grounding check only | — |
| `prompts/system_prompt.txt` | v1 benchmark system prompt — **reused unchanged** | — |
| `config.py` (section V2, bottom) | Every setting below | — |
v1 scripts (`1_…6_*.py`, `3_query_llm.py`, `4_query_gmaps.py`) are untouched.

## 2. Phase 2 — `4_query_gmaps_v2.py`
**What one query is:** route R, day D, slot S → Google Routes `computeRoutes` from the origin
landmark's Google coordinate to the destination's, departing at slot time S on day D of the
**reference week** (the Monday of next week at the time of the first real run, frozen in
`data/benchmark_v2/gmaps/run_manifest.json`).

**Request** (printed by `--dry-run`):
`travelMode DRIVE` · `routingPreference TRAFFIC_AWARE_OPTIMAL` + `trafficModel BEST_GUESS` · future `departureTime` (UTC) ·
`computeAlternativeRoutes true` · `polylineEncoding GEO_JSON_LINESTRING` · English, metric. No via points.
**Field mask:** duration, staticDuration, distanceMeters, description, routeLabels, polyline, legs start/end location,
step distance + navigation instruction. Traffic-on-polyline is deliberately **not** requested (it would move billing
from the Pro to the Enterprise SKU).

**Flow:** load routes → manifest (week + settings + checksum of `od_pairs.csv`) → 2,016 queries → skip those already OK in
`gmaps_responses.jsonl` → for each: call, append one JSON line immediately.

**Safety built in**
| Situation | Behaviour |
|---|---|
| `od_pairs.csv` changed after the run started | refuses to continue (checksum mismatch) — prevents mixing route lists |
| reference week has passed (e.g. resumed much later) | refuses; start a new run folder |
| 429 / 5xx / network error | retry with back-off 2, 4, 8, 16, 32 s |
| billing off / API disabled / bad key (403 etc.) | **stops at the first occurrence** with the fix from BILLING_AND_KEYS.md |
| other 4xx, or empty answer | stored as `status="error"` with the message; retried next run |
| 5 errors in a row | stops |
| interruption (Ctrl-C, crash) | everything already answered is on disk; rerun resumes |
Records hold: route/day/slot, departure (IST + UTC), status, error, all Google routes (distance, duration,
static duration, description, polyline, start/end location, steps), the exact request body (no key), timestamp, latency.

**Commands**
```
python 4_query_gmaps_v2.py --dry-run     # 2,016 calls, list price $20.16, expected $0 (5,000 free/month)
python 4_query_gmaps_v2.py --limit 1     # ONE real query for you to inspect   ← needs your approval
python 4_query_gmaps_v2.py               # the rest                              ← needs your approval
python 4_query_gmaps_v2.py --status
```

## 3. Phase 2 — `4b_process_gmaps_v2.py` (offline)
Per query (Google's first route):
1. distance, duration (predicted traffic), staticDuration (no traffic), **congestion ratio** = duration / staticDuration;
2. **endpoint check** — Google's start/end point vs our landmark coordinate; allowed = 150 m, or the landmark's own
   distance-to-road + 100 m for large sites (D-29). This is the "same origin/destination" guarantee;
3. **map-matching**: a point every 20 m along Google's line, snapped to the nearest OSM road within 25 m →
   ordered OSM road names (ground truth for road overlap), arterial share, unmatched fraction (quality);
4. road names parsed from Google's own instructions ("Turn left onto X") — independent cross-check;
5. hotspot share of Google's line.
Per route: **final tags** from the most frequent Google path over the 28 queries (tie → Wednesday MID_DAY, D-28), whether the group changed vs the
provisional OSM tags, number of distinct Google paths across the 28 queries, duration min/median/max, weekday and weekend
peak/night ratio. Outputs `gmaps_queries.csv`, `gmaps_routes.csv`, plots q1–q7 in `figures/phase2/`.

## 4. Phase 3 — `llm_clients.py`
`call_llm(model_key, system_prompt, user_prompt, schema, condition)` → `LLMResult` (parsed JSON, raw text,
model version reported by the API, prompt/output/**thought** tokens, latency, exact settings sent, error, error kind).
It never raises; error kinds: **fatal** (billing, disabled API, bad key, unknown model, malformed request) → stop run;
**retryable** (429, 5xx, network; honours Google's `retryDelay`) → wait and retry; **bad_output** (not JSON) → retry up to 3.
Gemini adapter: `google-genai` SDK, `response_json_schema` enforced, `temperature` explicit, `ThinkingConfig(thinking_level=…)`.
Adding GPT/Claude later = one adapter function + one entry in `V2_LLM_MODELS`.

## 5. Phase 3 — `3_query_llm_v2.py`
**Benchmark prompt (v1 wording + clock time, D-13/D-38):**
```
Origin: <origin llm_name>
Destination: <destination llm_name>
City: Bangalore, India
Day of the week: <Monday … Sunday>
Time of day: <Morning Rush (08:00) | Off-Peak (14:00) | Evening Rush (18:00) | Night (23:00)>
```
System prompt = v1 `prompts/system_prompt.txt`; schema = v1 `ROUTE_SCHEMA` field names/types + one-line descriptions (D-39).

| Subcommand | What it does | Calls |
|---|---|---|
| `select-consistency` | picks 10 routes, one per group, balanced by band / road type / exposure (done: `consistency_routes.csv`) | 0 |
| `grounding` | "Where exactly is <landmark>?" → locality, lat, lng, confidence; for the 64 landmarks used in routes | ~64 paid |
| `grounding-eval` | distance LLM point ↔ Google point; > 2 km = misplaced; flags routes with a misplaced endpoint (routes are flagged, not removed) | 0 |
| `benchmark --condition A --part main` | every query once, lowest thinking | 2,016 paid |
| `benchmark --condition A --part consistency` | 2 extra samples for the 10 routes | 560 paid |
| `benchmark --condition B` | every query once, high thinking — **last, separate approval** | 2,016 paid |
| `status` | progress + median thought tokens per file | 0 |
Record fields: route, day, slot, sample index, origin/destination ids + names, the exact prompt, condition, provider,
model name, **model version**, settings (temperature, thinking level), system-prompt hash, parsed + raw answer, token
counts incl. thinking, latency, attempts, status/error, `valid_numbers` (distance and time > 0).
Resume key = (route, day, slot, sample); errors are retried on the next run; fatal errors stop the run.

**Dry-run results (no network, gemini-3.8-flash):** grounding 64 calls ≈ $0.09 · condition A + consistency 2,576 calls ≈ $3.8 ·
condition B 2,016 calls ≈ $19 (thinking tokens are the uncertain part; the 1 test call will tell us the real count).
Queries are sent in a reproducible shuffled order (D-35).

## 6. How it was tested (all offline)
| Test | Result |
|---|---|
| Phase 1 refactor onto `v2_common.py` | `od_pairs.csv` byte-identical (md5 `cbb2e135…`) |
| `4_query_gmaps_v2.py --dry-run` | no network, no files created; sample request printed; 08:00 IST → 02:30 UTC correct |
| `--mock --limit 5` then `--mock` | 5 + 2,011 = 2,016, nothing repeated (resume works) |
| Fake HTTP: 200 / empty / 403 billing / 400 / 429×5 | ok / error / **fatal stop** / error / 5 back-off retries then error |
| `4b --mock` | 2,016 queries processed in ~50 s; endpoint tolerance works (large sites no longer false-flagged) |
| Fake Gemini SDK: success / bad JSON / 429 / 503 / billing / bad key / unknown model | ok (tokens + version read) / bad_output / retryable (17 s from retryDelay) / retryable / fatal / fatal / fatal |
| `ThinkingConfig(thinking_level=MINIMAL / HIGH)` built with the installed SDK | accepted |
| Mock LLM with 5 % injected failures, full A + consistency | 2,576 OK after 2,703 calls; rerun makes 0 calls |
| Fatal-stop (OpenAI stub) | stops after the first call, error stored |
Mock outputs: `data/benchmark_v2/mock/` (git-ignored, regenerable). They are **not** results.

## 7. Decisions
Decided 2026-10-01: OPTIMAL routing (D-27) · most-frequent-path tags (D-28) · A = `LOW`, B = `HIGH` on gemini-3.8-flash (D-26, D-36) ·
endpoint tolerance (D-29) · shuffled order (D-35). Still open: reference week (D-37), professor-level prompt/schema
tweaks (IO_SPEC §6.1), grounding flag rule, optional gemini-2.5-flash comparison, Batch API.
