# Benchmarking LLMs against Navigation Tools — Bangalore

How close can a large language model, using only its own knowledge, get to Google Maps on routes, distances and
travel times in Bangalore? The project has two parts:

1. **Traffic data pipeline:** Bangalore's official arterial and sub-arterial roads are geocoded and their Google Maps
   travel times are collected every two hours, then processed into congestion and variability statistics.
2. **LLM benchmark:** 72 routes between well-known landmarks, each asked at 08:00, 14:00, 18:00 and 23:00 on every day
   of a week (2,016 queries). Google Maps (predicted traffic) is the reference; Gemini and ChatGPT get only the place
   names, day and time, with no map or internet access.

Ishan Mehta · Supervisor: Prof. Vinayak Naik · Department of Computer Science, BITS Pilani, K K Birla Goa Campus

## Repository layout
```
src/
  preprocess/        1  road list -> geocoded coordinate chains (helpers/: OSM graph, WKT export, package check)
  scraper/           2  Routes API scrape every 2 h (scraper_v1/: earlier version)
  pipeline/          3  raw JSON -> flattened CSV tables
  analysis/          4  congestion, delay and variability statistics
  animation/         5  GeoPackage export for QGIS time animations
  llm_benchmark/     6  the benchmark (scripts numbered in run order; config.py holds every setting)
    prompts/            prompt files sent to the LLMs
    v1_pilot/           first version of the benchmark (superseded, kept for reference)
docs/
  benchmark/         methodology, exact prompts and requests, data dictionary, API setup, pilot audit
    round1/          original prompt: results, findings, figures
    round2/          neutral prompt, sub-routes, Gemini (ChatGPT pending): results, prompts, figures
  pipeline/          pipeline flowchart
  final_report/      the report (IEEE format, LaTeX)
data/                inputs and outputs (raw Google and LLM data is not published, see below)
  benchmark_v2/      benchmark inputs (landmarks, routes) and Round 1 outputs
  benchmark_round2/  Round 2 outputs
  benchmark/         pilot outputs
  processed/, raw/   pipeline data
```

## Setup
Python 3.14 (tested). Keys go in `.env`; see [docs/benchmark/API_KEYS_AND_BILLING.md](docs/benchmark/API_KEYS_AND_BILLING.md).
```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # then add your keys
```

## Running
Traffic pipeline (each script from its own folder):
```bash
python src/preprocess/1_geocode_roads.py          # then 2_remove_redundancy_routes.py, 3_transform_geocode_to_qgis_geometry.py
python src/scraper/main.py                         # runs until stopped; one snapshot every 2 h
python src/pipeline/data_pipeline.py               # -> output/flattened_traffic_data.csv, master_subroutes.csv
python src/analysis/geospatial_intermediate_analysis.py
python src/animation/animate_selected_routes.py --list-routes
```
LLM benchmark (from `src/llm_benchmark/`; paid calls only run without `--dry-run`, and every script has `--help`):

| Step | Script | What it does |
|---|---|---|
| 1 | `1b_build_od_pairs.py legs / geocode / pairs` | hotspot legs, landmark geocoding, the 72 routes |
| 2 | `4_query_gmaps_v2.py`, then `4b_process_gmaps_v2.py` | Google Maps answers and their road names |
| 3 | `3_query_llm_v2.py benchmark --condition A --part all` | LLM answers (`--model openai_main` for ChatGPT); `--part control` = format control |
| 4 | `5_compare_results_v2.py` | LLM vs Google: errors, time of day, traffic labels, roads, statistics |
| 5 | `6_report_figures_v2.py` | report figures |
| 6 | `7_subroutes_r2.py`, `8_prompt_effect.py`, `9_compare_models.py` | sub-routes, old vs neutral prompt, all models side by side |

Round 1 is the default; set `BENCHMARK_ROUND=2` for Round 2 (`--part subroutes` in step 2 adds the sub-route requests).
`--mock` runs any query script offline with fake answers.

## Results so far
- Gemini knows the landmarks and names real roads; distances are typically within 13–14 % of Google.
- Travel times are off by about 22 % and follow a city-wide stereotype: rush-hour trips are about twice the night time
  (Google: about 1.3 times) on all 72 routes. Removing the biased wording from the prompt mainly changed 08:00 and did
  not remove the stereotype.
- Details: [Round 1](docs/benchmark/round1/FINDINGS.md) · [Round 2](docs/benchmark/round2/RESULTS.md) ·
  [pilot audit](docs/benchmark/pilot_v1_audit.md). ChatGPT results will be added once collected.

## Data availability
Google Maps Platform terms restrict storing and redistributing its content, so raw Routes and Places responses and the
LLM answers are not in this repository. The scripts re-collect them, and the data is available on request. Published:
aggregate tables, figures, and the hand-made landmark list.
