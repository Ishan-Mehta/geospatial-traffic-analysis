"""
LLM vs Google Maps — Benchmark Configuration

All tunable parameters for the benchmark pipeline live here.
Change values here and re-run scripts — no code changes needed.
"""

import os
from pathlib import Path

# =====================================================================
#  BASE PATHS (auto-resolved relative to this config file)
# =====================================================================
_CONFIG_DIR = Path(__file__).resolve().parent          # src/llm_benchmark/
_PROJECT_ROOT = _CONFIG_DIR.parent.parent              # project root

ANALYSIS_RESULTS_DIR = _PROJECT_ROOT / "output" / "results"
MASTER_SUBROUTES_CSV = _PROJECT_ROOT / "output" / "master_subroutes.csv"

BENCHMARK_DIR = _PROJECT_ROOT / "data" / "benchmark"
BENCHMARK_ROUTES_CSV = BENCHMARK_DIR / "benchmark_routes.csv"
BENCHMARK_ROUTES_GEOCODED_CSV = BENCHMARK_DIR / "benchmark_routes_geocoded.csv"
LLM_RESPONSES_DIR = BENCHMARK_DIR / "llm_responses"
GMAPS_RESPONSES_DIR = BENCHMARK_DIR / "gmaps_responses"
COMPARISON_RESULTS_DIR = BENCHMARK_DIR / "results"
CHARTS_DIR = COMPARISON_RESULTS_DIR / "charts"

# =====================================================================
#  STEP 1 — ROUTE SELECTION
# =====================================================================
# How many routes to pick from each category.
# Adjust any value or comment out a category to skip it.
# Routes are de-duplicated, so the final set may be smaller than the sum.

SELECTION = {
    # Category label          : (count, source_csv_filename,             sort_order)
    "high_delay"              : (5,     "all_subroutes_by_delay.csv",    "top"),      # worst average delay
    "long_distance"           : (5,     "all_subroutes_by_distance.csv", "top"),      # longest routes
    "high_congestion"         : (5,     "all_subroutes_by_congestion_ratio.csv", "top"),  # highest congestion ratio
    "high_volatility"         : (5,     "all_subroutes_by_ratio_volatility.csv", "top"),  # most unpredictable
    "low_congestion"          : (5,     "all_subroutes_by_congestion_ratio.csv", "bottom"),  # smooth-flowing roads
}

# Columns shared across all ranked CSVs (after dropping the rank column)
COMMON_COLUMNS = [
    "sub_route_id", "road_name", "distance_meters",
    "avg_live_duration_s", "avg_delay_s", "max_delay_s", "delay_std_dev",
    "avg_congestion_ratio", "max_congestion_ratio", "ratio_std_dev",
    "avg_speed_kmph", "min_speed_kmph", "snapshot_count",
]

# =====================================================================
#  STEP 2 — REVERSE GEOCODING
# =====================================================================
GEOCODING_API_KEY_ENV = "GOOGLE_MAPS_API_KEY"     # env var name


# =====================================================================
#  STEP 3 — LLM CONFIGURATION
# =====================================================================
# Which model to query right now. Change this to switch models.
ACTIVE_MODEL = "gemini"

# Model registry — add new models here and they'll be available to query.
MODELS = {
    "gemini": {
        "model_name": "gemini-3.5-flash",
        "api_key_env": "GEMINI_API_KEY",          # env var name
    },
    # Uncomment / add more models as needed:
    # "gpt4o": {
    #     "model_name": "gpt-4o",
    #     "api_key_env": "OPENAI_API_KEY",
    # },
    # "claude": {
    #     "model_name": "claude-sonnet-4-20250514",
    #     "api_key_env": "ANTHROPIC_API_KEY",
    # },
}

# Path to the LLM system prompt template
SYSTEM_PROMPT_FILE = _CONFIG_DIR / "prompts" / "system_prompt.txt"

# =====================================================================
#  STEP 3 & 4 — TIME SLOTS & DAY TYPES
# =====================================================================
# Each time slot is tested for each benchmark route.
# "time" is in 24h HH:MM format (IST).

TIME_SLOTS = [
    {"id": "AM_PEAK",  "label": "Morning Rush",  "time": "08:00"},
    {"id": "MID_DAY",  "label": "Off-Peak",       "time": "14:00"},
    {"id": "PM_PEAK",  "label": "Evening Rush",   "time": "18:00"},
    {"id": "NIGHT",    "label": "Night",           "time": "23:00"},
]

DAY_TYPES = ["WEEKDAY", "WEEKEND"]

# =====================================================================
#  STEP 4 — GOOGLE MAPS API
# =====================================================================
GMAPS_API_KEY_ENV = "GOOGLE_MAPS_API_KEY"
GMAPS_ROUTES_URL = "https://routes.googleapis.com/directions/v2:computeRoutes"
GMAPS_FIELD_MASK = (
    "routes.duration,routes.staticDuration,routes.distanceMeters,"
    "routes.description,routes.travelAdvisory.speedReadingIntervals"
)
