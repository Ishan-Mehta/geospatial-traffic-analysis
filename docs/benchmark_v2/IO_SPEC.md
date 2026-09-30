# Exact inputs and outputs — Google Routes and LLM (v2)

Single source of truth for **what is sent** and **what comes back**, for both systems, and for the
**comparison row** that joins them. Values below are generated from the code (`4_query_gmaps_v2.py`,
`3_query_llm_v2.py`, `llm_clients.py`, `config.py`) — example route **R046, Wednesday, PM_PEAK**.
Status: approved choices as of 2026-10-01 (D-26…D-40). Compliance notes: [IMPORTANT_NOTES.md](IMPORTANT_NOTES.md).

---
## 1. What is held identical on both sides
| Aspect | Google Routes | LLM |
|---|---|---|
| Origin / destination | Google coordinate of the landmark (`od_pairs.csv` `origin_lat/lng`, `dest_lat/lng`) | the same landmark's `llm_name` |
| Day | slot's weekday inside the fixed reference week | weekday name (Monday … Sunday) |
| Time | exact clock time 08:00 / 14:00 / 18:00 / 23:00 IST | label + the same clock time: Morning Rush (08:00) / Off-Peak (14:00) / Evening Rush (18:00) / Night (23:00) (D-38) |
| Via points | none | none |
| Mode | car (`DRIVE`) | "car travel" (system prompt) |
| Traffic | predicted typical traffic for that departure | the model's own knowledge |

---
## 2. Google Routes — request
**Endpoint:** `POST https://routes.googleapis.com/directions/v2:computeRoutes`
**Headers:**
```
Content-Type: application/json
X-Goog-Api-Key: <from .env, never logged>
X-Goog-FieldMask: routes.duration,routes.staticDuration,routes.distanceMeters,routes.description,routes.routeLabels,routes.polyline.geoJsonLinestring,routes.legs.startLocation,routes.legs.endLocation,routes.legs.steps.distanceMeters,routes.legs.steps.navigationInstruction
```
**Body** (R046 Rajajinagar Metro Station → RV College of Engineering, Wednesday 18:00 IST = 12:30 UTC):
```json
{
  "origin":      {"location": {"latLng": {"latitude": 13.000345800000002, "longitude": 77.54974829999999}}},
  "destination": {"location": {"latLng": {"latitude": 12.9238466,         "longitude": 77.49850339999999}}},
  "travelMode": "DRIVE",
  "routingPreference": "TRAFFIC_AWARE_OPTIMAL",
  "departureTime": "2026-10-07T12:30:00Z",
  "computeAlternativeRoutes": true,
  "polylineEncoding": "GEO_JSON_LINESTRING",
  "languageCode": "en-US",
  "units": "METRIC",
  "trafficModel": "BEST_GUESS"
}
```
(Reference week pinned to Mon 5 – Sun 11 Oct 2026, D-37 — see §6.3.)
Billing SKU: **Compute Routes Pro** (triggered by TRAFFIC_AWARE_OPTIMAL). No traffic-on-polyline → not Enterprise.

## 3. Google Routes — output
**3a. Stored raw record** — one JSON line per query in `data/benchmark_v2/gmaps/gmaps_responses.jsonl`:
```json
{"route_id": "R046", "day": "Wednesday", "slot_id": "PM_PEAK", "slot_time": "18:00",
 "departure_ist": "2026-10-07T18:00:00+05:30", "departure_utc": "2026-10-07T12:30:00Z",
 "status": "ok", "error": null, "http_status": 200, "n_routes": 2,
 "routes": [
   {"distance_m": 12034, "duration_s": 2710, "static_duration_s": 1905,
    "description": "Chord Rd and Outer Ring Rd", "route_labels": ["DEFAULT_ROUTE"],
    "polyline": [[77.5497, 13.0003], "... [lng, lat] points ..."],
    "start_location": [13.0003, 77.5497], "end_location": [12.9238, 77.4985],
    "steps": [{"distance_m": 350, "maneuver": "DEPART", "instruction": "Head south on Dr Rajkumar Rd"}, "..."]},
   {"...": "alternative route, same fields"}],
 "request": {"...": "exact body above"}, "query_timestamp": "…", "latency_s": 0.8,
 "mock": false, "traffic_semantics": "predicted"}
```
(Numbers illustrative.) Failures: `"status": "error"`, `"error": "<plain-language reason>"`, `"routes": null` — retried next run.

**3b. Processed row** — `gmaps_queries.csv` (one per query, primary route = `routes[0]`):
`distance_m, duration_s, static_duration_s, congestion_ratio (= duration/static), endpoints_ok, osm_road_seq
("Dr Rajkumar Road | Chord Road | Outer Ring Road | Mysore Road"), google_step_roads, arterial_share_google,
hotspot_share_google, n_routes, …` — full list in [DATA_DICTIONARY.md](DATA_DICTIONARY.md).

---
## 4. LLM — request
**Model:** `gemini-3.8-flash` via the `google-genai` SDK, one independent `generate_content` call per query
(stateless: no chat history, no stored session — every call starts from a clean slate).

**System instruction** (`prompts/system_prompt.txt`, v1, unchanged):
```
You are a routing assistant for car travel in Bangalore, India.

IMPORTANT CONSTRAINTS:
- Do NOT use any external tool, mapping service, Google Maps, navigation agent, or real-time data source.
- Answer based ONLY on your general knowledge of Bangalore's road network and traffic patterns.
- You MUST provide numeric estimates even if uncertain. Do not refuse or say you cannot determine this.
- Consider the time of day and day of week when estimating travel time — Bangalore has heavy peak-hour traffic.
```
**User message** (v1 template + clock time, D-38; R046 Wednesday PM_PEAK):
```
Origin: Rajajinagar Metro Station
Destination: RV College of Engineering
City: Bangalore, India
Day of the week: Wednesday
Time of day: Evening Rush (18:00)
```
**Generation config:**
```
response_mime_type   = "application/json"
response_json_schema = ROUTE_SCHEMA (below)          # the API enforces this structure
temperature          = 1.0
thinking_config      = ThinkingConfig(thinking_level="LOW")    # condition A
                       ThinkingConfig(thinking_level="HIGH")   # condition B (last, separate approval)
```
**ROUTE_SCHEMA** (v1 field names, types and enum + one-line descriptions, D-39):
```json
{"type": "OBJECT",
 "required": ["suggested_route", "estimated_distance_km", "estimated_time_minutes", "traffic_awareness", "reasoning"],
 "properties": {
   "suggested_route":        {"type": "ARRAY", "items": {"type": "STRING"},
                              "description": "Ordered list of the road names you would drive on, from origin to destination (e.g. 'Hosur Road', 'Outer Ring Road'). Road names only."},
   "estimated_distance_km":  {"type": "NUMBER", "description": "Estimated driving distance in kilometres."},
   "estimated_time_minutes": {"type": "NUMBER", "description": "Estimated driving time in minutes at the given day and time of day, including expected traffic."},
   "traffic_awareness":      {"type": "STRING", "enum": ["none", "light", "moderate", "heavy"],
                              "description": "Expected traffic level along the route at that day and time."},
   "reasoning":              {"type": "STRING", "description": "Brief explanation of the route choice and the time estimate."}}}
```
**Grounding check** (separate, once per landmark; not part of benchmark prompts):
system = `prompts/grounding_system_prompt.txt`; user:
```
Place: Silk Board Junction
City: Bangalore, India
Where exactly is this place? Give its locality/area and your best estimate of its latitude and longitude.
```
schema: `{locality: STRING, latitude: NUMBER, longitude: NUMBER, confidence: enum[low, medium, high]}`.

## 5. LLM — output
**5a. What the model returns** (guaranteed to be valid JSON of this shape by `response_json_schema`):
```json
{"suggested_route": ["Dr Rajkumar Road", "Chord Road", "Outer Ring Road", "Mysore Road"],
 "estimated_distance_km": 13.5,
 "estimated_time_minutes": 55,
 "traffic_awareness": "heavy",
 "reasoning": "Wednesday evening rush on Chord Road and Mysore Road ..."}
```
**5b. Stored record** — one JSON line per query × sample in `llm/gemini_38_flash_A.jsonl`:
`route_id, day, slot_id, slot_label, sample_idx, origin_id, dest_id, origin_name, dest_name, prompt,
parsed_response (5a), raw_response, valid_numbers, condition, model_key, provider, model_name, model_version,
settings {model, temperature, thinking_level}, system_prompt_sha1, prompt_tokens, output_tokens, thought_tokens,
latency_s, attempts, status, error, error_kind, query_timestamp, mock`.

---
## 6. The comparison row (Phase 4 input) — how the two outputs line up
Join key: **(route_id, day, slot_id)** — identical on both sides by construction. One row per query × LLM sample.

| Comparison | LLM field | Google field | Metric |
|---|---|---|---|
| Distance | `estimated_distance_km` | `distance_m / 1000` (primary route) | ln(llm/google), abs error, over/under |
| Time (with traffic) | `estimated_time_minutes` | `duration_s / 60` | ln ratio, abs error, over/under |
| Time vs no-traffic | `estimated_time_minutes` | `static_duration_s / 60` | ln ratio (does the LLM add traffic?) |
| Traffic awareness | `traffic_awareness` → none 0, light 1, moderate 2, heavy 3 | `congestion_ratio` | Spearman ρ |
| Time-of-day sensitivity | peak/night ratio of `estimated_time_minutes` per route | peak/night ratio of `duration_s` | difference / correlation |
| Road validity | each name in `suggested_route` | all OSM street names in Bangalore | share that fuzzy-match (hallucination check) |
| Road overlap | set of `suggested_route` names | `osm_road_seq` (+ `google_step_roads`) | Jaccard |
| Consistency | `estimated_*` over sample_idx 0-2 | — | spread (CV) per query |
Rows carry the final tags (band, road type, hotspot exposure), `valid_numbers`, `endpoints_ok`, `grounding_flag`.
Road names are normalised before matching (lower-case, "Rd"→"Road", "Main Rd"→"Main Road", punctuation removed,
alias list e.g. "ORR" = "Outer Ring Road") — list finalised in Phase 4 and documented in METHODOLOGY.

### 6.1 Parseability
- The API enforces the JSON schema, so every answer has the same 5 fields; distance and time are numbers with fixed
  units (km, minutes); traffic is one of 4 fixed labels. No free-text parsing is needed for the numeric metrics.
  Invalid values (≤ 0) are flagged via `valid_numbers`.
- Road names: the schema description asks for an ordered list of road names only (D-39); normalisation + fuzzy
  matching handles remaining abbreviations ("ORR") and spelling variants.
- Time semantics: the prompt carries the exact clock time (D-38) and the schema says "including expected traffic",
  so `estimated_time_minutes` is compared with Google's `duration` (predicted traffic) for the same departure time.
- Not added (D-40): a separate free-flow-time field — possible later ablation.

### 6.2 LLM statelessness and order
Each call is independent (no history, no session, no caching of answers; paid-tier prompts are not used for
training). Queries are sent in a reproducible shuffled order (D-35) so any drift during the run (e.g. a silent model
update — detectable via `model_version`) spreads evenly across routes and groups.

### 6.3 Reference week for Google
Pinned to **Mon 5 – Sun 11 Oct 2026** (D-37). Sat 10 Oct = Mahalaya Amavasya (public holiday), Sun 11 Oct = Navaratri
begins; both are tagged via `calendar_note` and weekend results are reported with and without them. All Google queries
must be sent before **Mon 5 Oct 07:30 IST**; otherwise the week moves to Mon 26 Oct (`V2_REFERENCE_MONDAY` in config).
