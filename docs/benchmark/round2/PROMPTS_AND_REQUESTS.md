# Round 2 — prompts and API requests

Code: `src/llm_benchmark/3_query_llm_v2.py` (LLM), `4_query_gmaps_v2.py` (Google), `llm_clients.py` (providers),
`config.py` (settings; Round 2 is selected with `BENCHMARK_ROUND=2`). Round 1 prompts: [../IO_SPEC.md](../IO_SPEC.md).

## LLM prompt (identical for every model)
Instructions (`src/llm_benchmark/prompts/system_prompt_neutral.txt`):
```text
You are a routing assistant for car travel in Bangalore, India.

IMPORTANT CONSTRAINTS:
- Do NOT use any external tool, mapping service, Google Maps, navigation agent, or real-time data source.
- Answer based ONLY on your general knowledge of Bangalore's road network and traffic patterns.
- You MUST provide numeric estimates even if uncertain. Do not refuse or say you cannot determine this.
- Consider the time of day and day of week when estimating travel time.
```
Question (one per route × day × time; no date is given):
```text
Origin: <landmark>
Destination: <landmark>
City: Bangalore, India
Day of the week: <Monday … Sunday>
Time of day: <08:00 | 14:00 | 18:00 | 23:00>
```
Changes from Round 1: no "Bangalore has heavy peak-hour traffic", no time labels ("Morning Rush", "Off-Peak"), no example
road names, and no "including expected traffic" in the time fields.

Answer format (`ROUTE_SCHEMA_R2`): `suggested_route` = ordered list of `{road_name, distance_km, time_minutes}`, then
`estimated_distance_km`, `estimated_time_minutes` (totals at the given day and time), `traffic_awareness`
(none / light / moderate / heavy) and `reasoning`. The format control (`ROUTE_SCHEMA_R2_CONTROL`, 10 routes × 28 queries)
uses the same wording with `suggested_route` as a plain list of road names.

## LLM requests
| | Gemini | ChatGPT |
|---|---|---|
| Endpoint | `generativelanguage.googleapis.com/v1beta/models/gemini-3.8-flash:generateContent` | `api.openai.com/v1/responses` |
| Instructions / question | `systemInstruction` / `contents` | `instructions` / `input` |
| Answer format | `responseMimeType: application/json`, `responseJsonSchema` | `text.format` = `json_schema` (strict; same wording, OpenAI type spelling) |
| Settings | temperature 1.0, thinking level LOW (lowest available) | lowest reasoning effort; temperature 1.0 if the model accepts it |
| Other | no tools; each query a separate request | no tools; `store: false` |
Runs per model: 2,016 main + 560 repeats (10 routes × 28 × 2) + 280 format control; ChatGPT also gets the 64-landmark
location check (Gemini's Round 1 check is reused because that prompt has no traffic wording).

## Google Routes requests (`POST routes.googleapis.com/directions/v2:computeRoutes`)
Predicted traffic for the week Sat 28 Nov – Fri 4 Dec 2026, at 08:00 / 14:00 / 18:00 / 23:00 IST.

**Whole route** (one per query):
```json
{"origin": {"location": {"latLng": {"latitude": "<lat>", "longitude": "<lng>"}}},
 "destination": {"location": {"latLng": {"latitude": "<lat>", "longitude": "<lng>"}}},
 "travelMode": "DRIVE", "routingPreference": "TRAFFIC_AWARE_OPTIMAL", "trafficModel": "BEST_GUESS",
 "departureTime": "<UTC time of the slot>", "computeAlternativeRoutes": true,
 "polylineEncoding": "GEO_JSON_LINESTRING", "languageCode": "en-US", "units": "METRIC"}
```
Fields: route and leg duration, no-traffic duration and distance; polyline; step distance, no-traffic duration, start/end
and instruction (`V2_GMAPS_FIELD_MASK`).

**Sub-routes** (second request per query; skipped when the route stays on one road): Google gives traffic-aware time
only per leg, and a route without stops has one leg. The same body is sent with `computeAlternativeRoutes: false` and
one stop per road change on that query's own path:
`"intermediates": [{"via": false, "location": {"latLng": {...}, "heading": <direction of travel>}}]`.
Stops sit 40 m past the road change (one retry at 150 m if the legs differ by more than 2 % from the whole route), so a
stop never lands on the wrong level of a flyover or underpass. Exact per-road distances come from the steps.
