# 🚦 Geospatial Traffic Analysis — Bangalore

A multi-stage geospatial data engineering and statistical analysis pipeline for studying Bangalore's road traffic patterns. The system continuously collects live traffic data from Google Maps, processes it into structured datasets, and performs congestion/volatility analysis with rich visualizations.

## 📋 Table of Contents

- [Architecture](#architecture)
- [Pipeline Stages](#pipeline-stages)
- [Project Structure](#project-structure)
- [Setup](#setup)
- [Usage](#usage)
- [Notes](#notes)

## Architecture

```
┌─────────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────────┐     ┌───────────────┐
│   Preprocess    │────▶│   Scraper    │────▶│   Pipeline   │────▶│    Analysis     │────▶│   Animation   │
│                 │     │              │     │              │     │                  │     │               │
│ BBMP Road CSV   │     │ Google Maps  │     │ JSON → CSV   │     │ Congestion &     │     │ GeoPackage    │
│ → Geocoded      │     │ Routes API   │     │ Flattening   │     │ Bottleneck Stats │     │ Export for    │
│   Coordinates   │     │ (every 2hr)  │     │ + Spatial    │     │ + Visualizations │     │ QGIS Temporal │
│                 │     │              │     │   Hashing    │     │                  │     │ Animation     │
└─────────────────┘     └──────────────┘     └──────────────┘     └──────────────────┘     └───────────────┘
```

## Pipeline Stages

### Stage 1 — Preprocessing (`src/preprocess/`)
Converts BBMP road inventory CSV data into geocoded coordinate chains using the Google Geocoding API. Applies heuristic filtering to clean vague location names and produces optimized route coordinate chains.

**Scripts (run in order):**
1. `1_geocode_roads.py` — Geocode road names → lat/lng coordinate chains
2. `2_remove_redundancy_routes.py` — Remove duplicate/overlapping routes
3. `3_transform_geocode_to_qgis_geometry.py` — Convert to QGIS-compatible geometry

### Stage 2 — Data Collection (`src/scraper/`)
A daemon script that queries the Google Maps Routes API (`computeRoutes`) with `TRAFFIC_AWARE` routing every 2 hours. Saves raw JSON responses and CSV traffic summaries per run.

### Stage 3 — Data Pipeline (`src/pipeline/`)
Memory-efficient generator-based pipeline that processes the multi-GB raw JSON dataset. Flattens nested route legs into a unified CSV using MD5-based spatial hashing for deterministic sub-route identification.

### Stage 4 — Statistical Analysis (`src/analysis/`)
Merges live traffic durations with baseline (static) durations, using OSMnx as a fallback for missing speed-limit data. Generates:
- Congestion ratio rankings
- Bottleneck identification (by delay, speed, volatility)
- Distribution plots (delay, speed, congestion ratio, volatility)
- Top-N ranked bar charts and scatter plots
- Network health visualizations

### Stage 5 — QGIS Animation (`src/animation/`)
Exports selected routes as GeoPackage (`.gpkg`) files with speed-colored traffic segments for temporal animation in QGIS.

### Stage 6 — LLM Route Benchmarking (`src/llm_benchmark/`)
Benchmarks LLM routing predictions against live Google Maps Routes API data. Tests how accurately LLMs can estimate travel distance, time, and route choice for Bangalore roads using only minimal input (origin, destination, time of day, day of week).

**Scripts (run in order):**
1. `1_select_benchmark_routes.py` — Stratified selection of test routes by congestion, distance, volatility
2. `2_reverse_geocode.py` — One-time reverse geocoding of route coordinates to human-readable names
3. `3_query_llm.py` — Query LLM (Gemini) for route estimates with structured JSON output
4. `4_query_gmaps.py` — Query Google Maps Routes API for live/future ground truth
5. `5_compare_results.py` — Compare and compute metrics (distance %, time %, route match score)
6. `6_visualize_benchmark.py` — Generate benchmark charts and visualizations

**Configuration:** All parameters (route selection counts, time slots, LLM model, etc.) are configurable in `config.py`.
**Test:** Run `test_pipeline.py` for a single-route end-to-end smoke test.

## Project Structure

```
geospatial-traffic-analysis/
├── README.md
├── requirements.txt
├── .gitignore
├── .env.example
├── docs/
│   └── flowchart.pdf
├── src/
│   ├── preprocess/              # Stage 1: Road geocoding
│   │   ├── 1_geocode_roads.py
│   │   ├── 2_remove_redundancy_routes.py
│   │   ├── 3_transform_geocode_to_qgis_geometry.py
│   │   └── helpers/
│   │       ├── check_installed_packages.py
│   │       ├── graph_bangalore_osm.py
│   │       └── transform_geocode_to_qgis_wkt.py
│   ├── scraper/                 # Stage 2: Live data collection (active)
│   │   └── main.py
│   ├── scraper_v1/              # Stage 2: Original scraper (legacy)
│   │   └── main.py
│   ├── pipeline/                # Stage 3: JSON → CSV flattening
│   │   └── data_pipeline.py
│   ├── analysis/                # Stage 4: Statistical analysis
│   │   └── geospatial_intermediate_analysis.py
│   ├── animation/               # Stage 5: QGIS GeoPackage export
│   │   └── animate_selected_routes.py
│   └── llm_benchmark/           # Stage 6: LLM vs Maps Benchmark
│       ├── config.py
│       ├── test_pipeline.py
│       └── ...
├── data/
│   ├── raw/                     # Scraped JSON/CSV data (gitignored)
│   ├── processed/               # Geocoded road coordinates
│   ├── benchmark/               # Benchmark inputs/outputs
│   └── sample_response.json     # Example API response payload
└── output/                      # Generated results (gitignored)
```

> **Note:** `src/scraper_v1/` contains the original scraper implementation. `src/scraper/` is the actively used version with enhanced data capture (Google route descriptions, leg-level breakdown). Both are preserved for reference.

## Setup

### Prerequisites
- Python 3.9+
- A [Google Maps Platform API Key](https://console.cloud.google.com/google/maps-apis) with Routes API and Geocoding API enabled

### Installation

```bash
# Clone the repository
git clone https://github.com/<your-username>/geospatial-traffic-analysis.git
cd geospatial-traffic-analysis

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure API key
cp .env.example .env
# Edit .env and add your Google Maps API key
```

## Usage

### 1. Preprocess Road Data
```bash
cd src/preprocess
python 1_geocode_roads.py        # Geocode roads (interactive menu)
python 2_remove_redundancy_routes.py
python 3_transform_geocode_to_qgis_geometry.py
```

### 2. Start Traffic Data Collection
```bash
cd src/scraper
python main.py
# Runs continuously, fetching data every 2 hours
# Press Ctrl+C to stop
```

### 3. Run Data Pipeline
```bash
cd src/pipeline
python data_pipeline.py
# Processes all JSON files → flattened_traffic_data.csv + master_subroutes.csv
```

### 4. Run Statistical Analysis
```bash
cd src/analysis
python geospatial_intermediate_analysis.py
# Generates bottleneck CSVs and visualization PNGs in ./results/
```

### 5. Export QGIS Animations (Optional)
```bash
cd src/animation
python animate_selected_routes.py --list-routes          # See available routes
python animate_selected_routes.py --routes 1,5,10        # Export selected routes
```

### 6. Run LLM Benchmark
```bash
cd src/llm_benchmark
python 1_select_benchmark_routes.py   # Select benchmark routes
python 2_reverse_geocode.py           # One-time: geocode coordinates
python 3_query_llm.py                 # Query LLM for estimates
python 4_query_gmaps.py               # Query Google Maps for ground truth
python 5_compare_results.py           # Compare and compute metrics
python 6_visualize_benchmark.py       # Generate charts

# Or run a quick test with a single route:
python test_pipeline.py
```

## Notes

- Raw scraped data (~5GB) is not included in the repository. Place JSON files in `data/raw/` after collection.
- The analysis module downloads a ~150MB OSMnx graph of Bangalore on first run (cached locally as `.graphml`).
- All generated results (plots, CSVs, GeoPackages) are `.gitignore`-d as they are fully reproducible from the pipeline.
