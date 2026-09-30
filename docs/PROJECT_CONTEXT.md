# Geospatial MMI — Full Project Context

> **Purpose of this document:** This is a handoff context file for an AI agent continuing work on this project.
> The project is located at: `/Users/ishanmehta/Desktop/Projects/Geospatial_MMI/`

> **⚠️ Update 2026-09-30 — Stage 6 is being redesigned (v2).** The v1 benchmark below was audited and found ill-posed
> (see `docs/benchmark_v2/AUDIT_v1.md`). In particular the "22/112 done" status is wrong: only **1** of the 22 saved
> Gemini records has a response. Current work: branch `benchmark-v2`, docs in `docs/benchmark_v2/` (start at its README).
> The sections below describe v1 and are kept unchanged for the pilot/lessons-learned record.

---

## 1. Project Summary

A **Bangalore traffic analysis project** that:
1. Scrapes live traffic data from Google Maps Routes API for a set of Bangalore road segments
2. Processes and analyses the data (congestion, delay, speed, volatility)
3. **[CURRENT PHASE]** Benchmarks how well LLMs (Gemini) can predict routing vs. what Google Maps actually returns

The project is divided into 6 stages. Stages 1–5 are **complete**. Stage 6 (LLM Benchmark) is **in progress**.

---

## 2. Environment & Setup

| Item | Value |
|---|---|
| **Project root** | `/Users/ishanmehta/Desktop/Projects/Geospatial_MMI/` |
| **Python venv** | `maps_venv/` (inside project root) |
| **Activate venv** | `source maps_venv/bin/activate` |
| **Run scripts** | `cd src/llm_benchmark && python <script>.py` |
| **API keys** | Stored in `.env` at project root |
| **Key env vars** | `GOOGLE_MAPS_API_KEY`, `GEMINI_API_KEY` |

### `.env` structure
```
GOOGLE_MAPS_API_KEY=...   # Used for: geocoding, live Maps queries
GEMINI_API_KEY=...         # Used for: Gemini LLM queries (free tier)
```

### Installed packages (key ones)
```
pandas, numpy, requests, python-dotenv, geopandas, osmnx, networkx,
shapely, matplotlib, seaborn, google-genai (v2.22.0)
```

---

## 3. Project Directory Structure

```
Geospatial_MMI/
├── .env                          # API keys (gitignored)
├── .env.example                  # Template for .env
├── requirements.txt              # Python dependencies
├── README.md                     # Project overview
│
├── src/
│   ├── preprocess/               # Stage 1: Road geocoding
│   ├── scraper/                  # Stage 2: Live traffic scraper (active version)
│   ├── scraper_v1/               # Stage 2: Original scraper (legacy)
│   ├── pipeline/                 # Stage 3: JSON → CSV processing
│   ├── analysis/                 # Stage 4: Statistical analysis
│   ├── animation/                # Stage 5: QGIS export
│   └── llm_benchmark/            # Stage 6: LLM benchmark [CURRENT WORK]
│       ├── config.py             # ← All tunable parameters live here
│       ├── 1_select_benchmark_routes.py
│       ├── 2_reverse_geocode.py
│       ├── 3_query_llm.py
│       ├── 4_query_gmaps.py
│       ├── 5_compare_results.py
│       ├── 6_visualize_benchmark.py
│       ├── test_pipeline.py      # E2E smoke test (single route)
│       └── prompts/
│           └── system_prompt.txt
│
├── data/
│   ├── raw/                      # Scraped JSON (gitignored)
│   ├── processed/                # Geocoded road coords
│   └── benchmark/                # [CURRENT WORK] Benchmark data
│       ├── benchmark_routes.csv          # Generated (20 routes -> 14 after filtering)
│       ├── benchmark_routes_geocoded.csv # Generated (14 intra-Bangalore routes)
│       ├── llm_responses/
│       │   └── gemini_20260923_213203.jsonl  # PARTIAL (22/112 queries done)
│       ├── gmaps_responses/      # Empty (not started)
│       └── results/              # Empty (not started)
│
└── output/                       # Analysis outputs (from Stage 4)
    ├── master_subroutes.csv      # All sub-routes with coordinates
    └── results/                  # 8 ranked CSVs + 12 chart PNGs
```

---

## 4. Stages 1–5 (Completed)

### Stage 1 — Preprocess (`src/preprocess/`)
Geocodes a set of manually chosen Bangalore road names into lat/lng coordinates using OSMnx. Outputs road geometries used by the scraper.

### Stage 2 — Scraper (`src/scraper/main.py`)
- Hits Google Maps Routes API (`computeRoutes`) every N minutes
- Stores raw JSON responses in `data/raw/`
- API endpoint: `https://routes.googleapis.com/directions/v2:computeRoutes`
- Uses: `TRAFFIC_AWARE` routing, captures `duration`, `staticDuration`, `distanceMeters`, `speedReadingIntervals`
- Headers: `X-Goog-Api-Key`, `X-Goog-FieldMask`

### Stage 3 — Pipeline (`src/pipeline/data_pipeline.py`)
Flattens raw JSON to CSV. Produces `master_subroutes.csv`. Key columns: `sub_route_id`, `start_lat/lng`, `end_lat/lng`, `distance_meters`, `live_duration_s`, `static_duration_s`.

### Stage 4 — Analysis (`src/analysis/`)
Statistical analysis over all scraped snapshots. Produces:
- 8 ranked CSVs in `output/results/` (by delay, congestion, speed, volatility, distance)
- 12 visualization plots
- Key computed columns: `avg_delay_s`, `avg_congestion_ratio` (= delay/static_duration), `ratio_std_dev`, `avg_speed_kmph`

### Stage 5 — Animation (`src/animation/`)
Exports GeoPackage files for QGIS temporal animation with speed-colored segments.

---

## 5. Stage 6 — LLM Benchmark (Current Work)

### Goal
Compare LLM routing predictions vs. live Google Maps ground truth for the same origin-destination pairs, time slots, and day types.

**Research question:** How accurately can Gemini estimate travel distance and time for Bangalore roads using only minimal inputs (origin, destination, time of day, day of week)?

### Benchmark Design
- **14 routes** — selected from Stage 4 analysis output, stratified across 5 categories
- **4 time slots** — AM Peak (08:00), Mid Day (14:00), PM Peak (18:00), Night (23:00)
- **2 day types** — WEEKDAY (Wednesday), WEEKEND (Saturday)
- **Total queries** — 14 × 4 × 2 = **112 per LLM model**

### Route Categories
| Category | Count | What it means |
|---|---|---|
| `high_delay` | 3 routes | Worst average delay (bottleneck roads) |
| `high_congestion` | 4 routes | Highest congestion ratio (delay/static_duration) |
| `high_volatility` | 2 routes | Most unpredictable (high std_dev) |
| `low_congestion` | 5 routes | Smooth-flowing roads |

> Note: `long_distance` category (5 routes) was dropped — those routes had endpoints far outside Bangalore (Hiriyur, Shivamogga, 150–380km away). 14 routes remain, all intra-Bangalore.

### LLM Prompt Design
- **System prompt:** "Do NOT use Google Maps, navigation tools, or real-time data. Use only general knowledge of Bangalore's road network."
- **User prompt format:**
  ```
  Origin: <locality name>
  Destination: <locality name>
  City: Bangalore, India
  Day of the week: Wednesday / Saturday
  Time of day: Morning Rush / Off-Peak / Evening Rush / Night
  ```
- Structured output enforced via `response_json_schema` (no schema example in prompt — per SDK docs this degrades quality)

### LLM Response Schema
```json
{
  "suggested_route": ["Road A", "Road B"],
  "estimated_distance_km": 11.5,
  "estimated_time_minutes": 55,
  "traffic_awareness": "heavy",
  "reasoning": "..."
}
```

### Metrics to Compute (Step 5)
| Metric | Formula |
|---|---|
| `dist_error_pct` | `(llm_dist_km × 1000 - gmaps_dist_m) / gmaps_dist_m × 100` |
| `time_vs_live_error_pct` | `(llm_time_min × 60 - gmaps_live_s) / gmaps_live_s × 100` |
| `time_vs_static_error_pct` | `(llm_time_min × 60 - gmaps_static_s) / gmaps_static_s × 100` |
| `abs_dist_error_km` | Absolute distance difference |
| `abs_time_error_min` | Absolute time difference |
| `route_match_score` | `difflib.SequenceMatcher` ratio: LLM route string vs GMaps description |

---

## 6. The 14 Benchmark Routes

From `data/benchmark/benchmark_routes_geocoded.csv`:

| # | Category | Road Name | Origin | Destination | Distance |
|---|---|---|---|---|---|
| 1 | high_delay | 7th Cross Dinnur Rd – Ambedkar Rd | Dooravani Nagar | Vishveshwaraya Nagar | 30.3 km |
| 2 | high_delay | Avenue Road Palace Road | Avenue Road | Nagarathpete | 1.5 km |
| 3 | high_delay | KR Puram Railway Station Road | Ramamurthy Nagar | Chandra Layout | 27.1 km |
| 4 | high_congestion | J.C. Road | Avenue Road | J.C. Road | 0.75 km |
| 5 | high_congestion | T.C.M Royan Road | Majestic | Sultanpete | 1.5 km |
| 6 | high_congestion | Mysore-Old Madras Road | Mysore (Kengeri) | Kengeri | 1.3 km |
| 7 | high_congestion | Tumkur Road @ Yeshvanthpur | Tumkur Rd (Rajajinagar) | Yeshvanthpur Bus Station | 0.29 km |
| 8 | high_volatility | B.Narayanaswamappa Road | Start (Yeswanthpur) | End (Yeswanthpur) | 0.27 km |
| 9 | high_volatility | Davis Road | Start (Richards Town) | End (Richards Town) | 0.5 km |
| 10 | low_congestion | Whitefield–Kaggadasapura Main Rd | Whitefield | Jeevan Bima Nagar | 16.0 km |
| 11 | low_congestion | Banasawadi–Channasandra Main Rd | Banasawadi Road | Channasandra Main Road | 0.47 km |
| 12 | low_congestion | 29th Main Road BTM Layout | Start (BTM Layout) | End (BTM Layout) | 0.45 km |
| 13 | low_congestion | 3rd Cross 13th Main Saidarshan Rd | 3rd Cross (Domlur) | 10th Main (Domlur) | 35 m |
| 14 | low_congestion | Cubbon Park Road | Bengaluru | Ashok Nagar | 0.16 km |

---

## 7. Gemini API — Critical Notes

### SDK
- Package: `google-genai` v2.22.0
- Import: `from google import genai` and `from google.genai import types`
- **DO NOT** use `google-generativeai` (deprecated)

### Correct call pattern
```python
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
response = client.models.generate_content(
    model="gemini-3.5-flash",
    contents=prompt_text,
    config=types.GenerateContentConfig(
        response_mime_type="application/json",
        response_json_schema=ROUTE_SCHEMA,
        system_instruction=system_prompt,
        thinking_config=types.ThinkingConfig(thinking_budget=0),  # MUST set — disables thinking
    ),
)
result = json.loads(response.text)
```

### Free Tier Rate Limits — THE CURRENT BLOCKER
- `gemini-3.5-flash` free tier: **20 requests per day**
- 112 queries needed → 6 days OR enable billing (~₹1 total)
- `gemini-2.5-flash` returns 404 for new users — use `gemini-3.5-flash`
- `thinking_budget=0` is critical — without it, each query takes 30–60 seconds
- Script has **auto-resume** — detects latest `.jsonl` and skips completed queries

### Available models (verified with the project's API key)
`gemini-3.5-flash` (active), `gemini-3.5-flash-lite`, `gemini-3.6-flash`, `gemini-3.7-flash`, `gemini-3.8-flash`, `gemini-2.5-flash`, `gemini-2.5-pro`

---

## 8. Google Maps Routes API — Notes

- **Endpoint:** `https://routes.googleapis.com/directions/v2:computeRoutes`
- **Auth:** `X-Goog-Api-Key` header (not query param)
- **Field mask:** `routes.duration,routes.staticDuration,routes.distanceMeters,routes.description,routes.travelAdvisory.speedReadingIntervals`
- Routing: `TRAFFIC_AWARE`, `travelMode: DRIVE`
- Future departure: `departureTime` as UTC ISO 8601 (convert from IST using `zoneinfo`)
- `duration` = live time (with traffic), `staticDuration` = no-traffic baseline
- `delay_s = duration - staticDuration` (positive = congested, negative = unusually fast)

---

## 9. Current Status

| Step | Script | Status |
|---|---|---|
| 1. Select routes | `1_select_benchmark_routes.py` | Done |
| 2. Reverse geocode | `2_reverse_geocode.py` | Done |
| 3. LLM queries | `3_query_llm.py` | **PARTIAL — 22/112 saved** |
| 4. GMaps queries | `4_query_gmaps.py` | Not started |
| 5. Compare | `5_compare_results.py` | Not started |
| 6. Visualize | `6_visualize_benchmark.py` | Not started |

### To resume
```bash
source maps_venv/bin/activate
cd src/llm_benchmark
python 3_query_llm.py    # auto-resumes from query 23
# then after it finishes:
python 4_query_gmaps.py
python 5_compare_results.py
python 6_visualize_benchmark.py
```

**First resolve the rate limit:** Enable billing on the GCP project linked to `GEMINI_API_KEY`, or wait and run 20 queries per day using the resume feature.

---

## 10. Key Design Decisions

1. **No re-geocoding of LLM route** — Only compare LLM's stated estimates (distance, time) against GMaps for same OD pair. Don't re-route LLM's suggested roads.
2. **Minimal context to LLM** — Only origin, destination, time of day, day of week. Professor's explicit requirement.
3. **Future departure time** — Next Wednesday/Saturday at target time IST → UTC for predictive GMaps routing.
4. **Intra-Bangalore only** — 6 routes with coordinates outside Bangalore dropped.
5. **JSONL format** — One JSON object per line, appended after every query. Safe to interrupt and resume.
6. **`thinking_budget=0`** — Must disable thinking or free-tier queries silently hang for 30–60s each.
