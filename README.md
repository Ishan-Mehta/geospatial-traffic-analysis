# Benchmarking LLMs against Navigation Tools — Bangalore

How close can a large language model, using only its own knowledge, get to Google Maps on routes, distances and travel
times in Bangalore? The project builds a Bangalore traffic dataset and then benchmarks LLMs (Gemini; ChatGPT in
progress) against Google Maps on the same trips.

**Ishan Mehta** · Supervisor: **Prof. Vinayak Naik** · Department of Computer Science, BITS Pilani, K K Birla Goa Campus

## Contents
- [Pipeline stages](#pipeline-stages)
- [Project structure](#project-structure)
- [Setup](#setup)
- [Usage](#usage)
- [Results](#results)
- [Data availability](#data-availability)
- [Notes](#notes)

## Pipeline stages
The project has two parts: a live traffic analysis of Bangalore's main roads (Stages 1–5) and the LLM benchmark (Stage 6).

```
 Part A — Traffic analysis                                         Part B — LLM benchmark
 ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     ┌──────────────────────┐
 │ 1 Preprocess │─▶│ 2 Scraper    │─▶│ 3 Pipeline   │─▶│ 4 Analysis   │─▶│ 5 Animation  │     │ 6 LLM vs Google Maps │
 │ BBMP roads → │  │ Routes API   │  │ JSON → flat  │  │ congestion,  │  │ GeoPackage   │ ──▶ │ 72 landmark routes,  │
 │ coordinates  │  │ every 2 h    │  │ CSV tables   │  │ variability  │  │ for QGIS     │     │ hotspots from Stage 4│
 └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘     └──────────────────────┘
```

**Part A — Traffic analysis** (`src/preprocess` … `src/animation`)
1. **Preprocess:** the BBMP lists of arterial and sub-arterial roads are geocoded into coordinate chains (Google
   Geocoding API), vague place names are filtered out, and duplicate or overlapping routes are removed.
2. **Scraper:** every route is queried on the Google Maps Routes API (traffic-aware) every two hours; raw JSON and a CSV
   summary are saved per snapshot.
3. **Pipeline:** the raw JSON is streamed and flattened into a time-series table plus a master table of route legs
   (stable leg IDs from hashed coordinates).
4. **Analysis:** delay, speed, congestion and variability per leg; bottleneck rankings and plots. The most variable
   legs become the "hotspots" used in Stage 6.
5. **Animation:** selected routes are exported as GeoPackages, coloured by traffic, for QGIS time animations.

**Part B — LLM benchmark** (`src/llm_benchmark`)
- **Routes:** 70 well-known landmarks (metro stations, junctions, hospitals, tech parks…) are located from their names,
  checked and reviewed, giving 72 routes of 1–29 km balanced by length, road type and hotspot exposure.
- **Queries:** each route at 08:00, 14:00, 18:00 and 23:00 on every day of one week = 2,016 queries.
- **Reference:** Google Maps predicted traffic (`TRAFFIC_AWARE_OPTIMAL`) for that week, with road names map-matched to
  OpenStreetMap.
- **LLMs:** get only the landmark names, day and time (no map, no tools) and return a route, distance, time and traffic
  level. Repeats, a landmark-location check and a simple distance-and-speed formula serve as checks and baseline.
- **Rounds:**

  | | Prompt | Google week | Extra | Models |
  |---|---|---|---|---|
  | Pilot (v1) | first design, 14 short road segments | — | — | Gemini |
  | Round 1 | original prompt (time labels such as "Morning Rush") | 5–11 Oct 2026 | — | Gemini |
  | Round 2 | neutral prompt (clock time only) | 28 Nov – 4 Dec 2026 | sub-routes (road-by-road distance and time) | Gemini; ChatGPT pending |

## Project structure
```
.
├── README.md · requirements.txt · .env.example
├── src/
│   ├── preprocess/              Stage 1: 1_geocode_roads → 2_remove_redundancy_routes → 3_transform_geocode_to_qgis_geometry
│   │   └── helpers/             OSM graph download, WKT export, package check
│   ├── scraper/                 Stage 2: main.py (scraper_v1/ = earlier version)
│   ├── pipeline/                Stage 3: data_pipeline.py
│   ├── analysis/                Stage 4: geospatial_intermediate_analysis.py
│   ├── animation/               Stage 5: animate_selected_routes.py
│   └── llm_benchmark/           Stage 6 (scripts numbered in run order)
│       ├── config.py            every setting (routes, slots, models, prices, Round 2 switch)
│       ├── llm_clients.py       Gemini and OpenAI adapters (+ offline mock)
│       ├── v2_common.py         shared helpers
│       ├── prompts/             prompt files sent to the LLMs
│       └── v1_pilot/            pilot scripts (superseded)
├── docs/
│   ├── pipeline/                pipeline flowchart
│   ├── benchmark/               methodology, prompts and requests, data dictionary, API setup, pilot audit
│   │   ├── round1/              results, findings, figures
│   │   └── round2/              results, prompts and requests, figures per model
│   └── final_report/            the report (IEEE, LaTeX)
├── data/
│   ├── raw/, processed/         Part A inputs (raw scrape not published)
│   ├── benchmark_v2/            benchmark inputs (landmarks, routes) and Round 1 summaries and figures
│   ├── benchmark_round2/        Round 2 summaries and figures (per model)
│   └── benchmark/               pilot outputs
└── output/                      Part A outputs (git-ignored)
```

## Setup
**Prerequisites:** Python 3.14 (tested), and API keys for Google Maps Platform (Routes, Places, Geocoding), Gemini and,
for ChatGPT, OpenAI. Key setup, billing and common errors: [docs/benchmark/API_KEYS_AND_BILLING.md](docs/benchmark/API_KEYS_AND_BILLING.md).

**Installation**
```bash
git clone https://github.com/Ishan-Mehta/geospatial-traffic-analysis.git
cd geospatial-traffic-analysis
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # add GOOGLE_MAPS_API_KEY, GEMINI_API_KEY, CHATGPT_API_KEY
```

## Usage
### Part A — Traffic analysis (run each script from its folder)
```bash
cd src/preprocess  && python 1_geocode_roads.py && python 2_remove_redundancy_routes.py && python 3_transform_geocode_to_qgis_geometry.py
cd src/scraper     && python main.py                       # runs until stopped, one snapshot every 2 h
cd src/pipeline    && python data_pipeline.py              # -> output/flattened_traffic_data.csv, master_subroutes.csv
cd src/analysis    && python geospatial_intermediate_analysis.py
cd src/animation   && python animate_selected_routes.py --list-routes   # then --routes 1,5,10
```

### Part B — LLM benchmark (from `src/llm_benchmark/`)
Every script has `--help`. Calls that cost money run only without `--dry-run`; `--dry-run` shows the count, cost and a
sample request, `--limit 1` makes one real call, and `--mock` runs offline with fake answers. Runs resume where they
stopped.

| Step | Command | Output |
|---|---|---|
| 1 Routes | `python 1b_build_od_pairs.py legs`, `geocode`, `pairs` | hotspot legs, landmark coordinates, the 72 routes |
| 2 Google | `python 4_query_gmaps_v2.py`, then `python 4b_process_gmaps_v2.py` | Google answers, road names, route tags |
| 3 LLM | `python 3_query_llm_v2.py benchmark --condition A --part all` | LLM answers (+ repeats) |
| 4 Compare | `python 5_compare_results_v2.py` | errors, time of day, traffic labels, roads, statistics |
| 5 Figures | `python 6_report_figures_v2.py` | report figures |

**Round 2** (set `BENCHMARK_ROUND=2`; outputs go to `data/benchmark_round2/` and `docs/benchmark/round2/`):
```bash
export BENCHMARK_ROUND=2
python 4_query_gmaps_v2.py && python 4_query_gmaps_v2.py --part subroutes && python 4b_process_gmaps_v2.py
python 3_query_llm_v2.py benchmark --condition A --part all                 # Gemini (default model)
python 3_query_llm_v2.py benchmark --condition A --part control             # format control
python 3_query_llm_v2.py --model openai_main benchmark --condition A --part all   # ChatGPT (also: grounding)
python 5_compare_results_v2.py --model gemini_38_flash                      # repeat steps 4-5 per model
python 7_subroutes_r2.py --model gemini_38_flash                            # sub-routes vs Google
python 8_prompt_effect.py --model gemini_38_flash                           # original vs neutral prompt
python 9_compare_models.py                                                  # Google vs all models side by side
```

## Results
- Gemini knows the landmarks (all placed correctly, typically ~250 m off) and names real roads (≥ 95 %); distances are
  typically within 13–14 % of Google.
- Travel times miss by about 22 % and follow a city-wide stereotype: rush-hour trips take about twice as long as at
  night (Google: about 1.3 times), on all 72 routes, with short trips exaggerated most.
- The neutral prompt mainly changed 08:00 (fewer "heavy" labels, shorter times) but did not remove the stereotype.
  Road-by-road estimates are much less accurate than the totals (errors cancel out).

Details: [Round 1 findings](docs/benchmark/round1/FINDINGS.md) · [Round 2 results](docs/benchmark/round2/RESULTS.md) ·
[methodology](docs/benchmark/METHODOLOGY.md) · [pilot audit](docs/benchmark/pilot_v1_audit.md).

## Data availability
Google Maps Platform terms restrict storing and redistributing its content, so the raw scrape, the raw Routes and Places
responses and the LLM answers are not in this repository. The scripts re-collect them, and the data is available on
request. Published: aggregate tables, figures, the hand-made landmark list, and a sample API response.

## Notes
- API keys live only in `.env` (git-ignored); scripts never print them.
- Google benchmark times are Google's **predicted** traffic for the stated week, not live measurements.
- Stage 4 downloads the Bangalore OpenStreetMap drive graph on first run (~150 MB, cached as `.graphml`).
- Each LLM query is a separate request with no chat history; model versions, settings and token counts are stored with
  every answer.
