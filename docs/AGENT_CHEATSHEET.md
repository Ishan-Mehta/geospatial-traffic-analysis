# LLM Benchmark — Agent Cheatsheet

Quick reference for continuing Stage 6 of the Geospatial MMI project.
Full context: `docs/PROJECT_CONTEXT.md`

---

## Immediate Next Steps

### Step 1 — Finish LLM queries (3_query_llm.py)

**Status:** 22/112 done. Partial file: `data/benchmark/llm_responses/gemini_20260923_213203.jsonl`

**Blocker:** Free tier = 20 req/day on `gemini-3.5-flash`. Either:
- Enable billing on GCP project linked to `GEMINI_API_KEY` (~₹1 total cost)
- OR run 20/day over 6 days (resume is automatic)

```bash
source maps_venv/bin/activate
cd src/llm_benchmark
python 3_query_llm.py   # auto-resumes, skips first 22
```

### Step 2 — Run GMaps queries (4_query_gmaps.py)

Queries live/future Google Maps for the same 14 routes × 4 slots × 2 day types.
Run only after Step 1 finishes (needs geocoded CSV but not LLM data).
Actually can be run in parallel with Step 1.

```bash
python 4_query_gmaps.py
```

Output: `data/benchmark/gmaps_responses/gmaps_live_<timestamp>.json`

### Step 3 — Compare (5_compare_results.py)

Joins LLM + GMaps results, computes all error metrics, saves CSVs.

```bash
python 5_compare_results.py
```

Output:
- `data/benchmark/results/benchmark_comparison.csv`
- `data/benchmark/results/summary_stats.csv`

### Step 4 — Visualize (6_visualize_benchmark.py)

```bash
python 6_visualize_benchmark.py
```

Output: 6 charts in `data/benchmark/results/charts/`

---

## Config Reference (config.py)

```python
ACTIVE_MODEL = "gemini"           # change to switch models
MODELS = {
    "gemini": {
        "model_name": "gemini-3.5-flash",   # verified working
        "api_key_env": "GEMINI_API_KEY",
    }
}
TIME_SLOTS = [
    {"id": "AM_PEAK",  "label": "Morning Rush",  "time": "08:00"},
    {"id": "MID_DAY",  "label": "Off-Peak",       "time": "14:00"},
    {"id": "PM_PEAK",  "label": "Evening Rush",   "time": "18:00"},
    {"id": "NIGHT",    "label": "Night",           "time": "23:00"},
]
DAY_TYPES = ["WEEKDAY", "WEEKEND"]
```

---

## Key File Paths

```
src/llm_benchmark/config.py                          # all config
src/llm_benchmark/prompts/system_prompt.txt          # LLM system prompt
data/benchmark/benchmark_routes_geocoded.csv         # 14 routes with names + coords
data/benchmark/llm_responses/gemini_20260923_213203.jsonl  # partial LLM output
data/benchmark/gmaps_responses/                      # GMaps output goes here
data/benchmark/results/                              # comparison CSVs + charts
output/master_subroutes.csv                          # all scraped routes (reference)
output/results/                                      # Stage 4 ranked CSVs
```

---

## Gemini SDK Quick Reference

```python
from google import genai
from google.genai import types
import os, json
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).resolve().parent.parent.parent / '.env')
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

SCHEMA = {
    'type': 'OBJECT',
    'required': ['suggested_route', 'estimated_distance_km',
                 'estimated_time_minutes', 'traffic_awareness', 'reasoning'],
    'properties': {
        'suggested_route': {'type': 'ARRAY', 'items': {'type': 'STRING'}},
        'estimated_distance_km': {'type': 'NUMBER'},
        'estimated_time_minutes': {'type': 'NUMBER'},
        'traffic_awareness': {'type': 'STRING',
                              'enum': ['none', 'light', 'moderate', 'heavy']},
        'reasoning': {'type': 'STRING'},
    },
}

response = client.models.generate_content(
    model='gemini-3.5-flash',
    contents=user_prompt,
    config=types.GenerateContentConfig(
        response_mime_type='application/json',
        response_json_schema=SCHEMA,
        system_instruction=system_prompt,
        thinking_config=types.ThinkingConfig(thinking_budget=0),  # CRITICAL
    ),
)
result = json.loads(response.text)
```

---

## Google Maps Routes API Quick Reference

```python
import requests, datetime
from zoneinfo import ZoneInfo

def get_departure_time(day_type, time_str):
    ist = ZoneInfo("Asia/Kolkata")
    now = datetime.datetime.now(ist)
    target_weekday = 2 if day_type == "WEEKDAY" else 5  # Wed=2, Sat=5
    t_hour, t_min = map(int, time_str.split(':'))
    days_ahead = (target_weekday - now.weekday()) % 7 or 7
    target = (now + datetime.timedelta(days=days_ahead)).replace(
        hour=t_hour, minute=t_min, second=0, microsecond=0)
    return target.astimezone(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

payload = {
    'origin': {'location': {'latLng': {'latitude': start_lat, 'longitude': start_lng}}},
    'destination': {'location': {'latLng': {'latitude': end_lat, 'longitude': end_lng}}},
    'travelMode': 'DRIVE',
    'routingPreference': 'TRAFFIC_AWARE',
    'departureTime': get_departure_time("WEEKDAY", "08:00"),
}
headers = {
    'Content-Type': 'application/json',
    'X-Goog-Api-Key': os.getenv("GOOGLE_MAPS_API_KEY"),
    'X-Goog-FieldMask': 'routes.duration,routes.staticDuration,routes.distanceMeters,routes.description,routes.travelAdvisory.speedReadingIntervals',
}
resp = requests.post('https://routes.googleapis.com/directions/v2:computeRoutes',
                     headers=headers, json=payload)
data = resp.json()
route = data['routes'][0]
live_s   = int(route['duration'].rstrip('s'))
static_s = int(route['staticDuration'].rstrip('s'))
dist_m   = route['distanceMeters']
delay_s  = live_s - static_s  # positive = traffic, negative = unusually fast
```

---

## Known Issues / Gotchas

1. **Rate limit:** `gemini-3.5-flash` free tier = 20 req/day. Script auto-resumes.
2. **Thinking mode:** Must set `thinking_budget=0` or queries hang 30–60s silently.
3. **Very short routes (< 500m):** Routes 4–9, 11–14 are tiny road segments. LLM will estimate poorly. Results still useful for analysis — just note this when interpreting metrics.
4. **Route 13** (35m length) — trivially short, may want to exclude from distance error analysis.
5. **`pytz` not installed** — use stdlib `zoneinfo` for timezone handling (already done in scripts).
6. **GMaps `duration` field** includes trailing `'s'` — strip with `.rstrip('s')` before `int()`.
7. **5_compare_results.py** reads both `.json` and `.jsonl` — uses `load_responses()` helper.
8. **LLM data is nested** — `parsed_response` is a dict inside each JSONL record, not at top level.
