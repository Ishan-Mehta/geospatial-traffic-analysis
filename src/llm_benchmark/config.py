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


# =====================================================================
#  V2 BENCHMARK (branch benchmark-v2) — see docs/benchmark_v2/
#  v1 constants above are left unchanged for the pilot section.
# =====================================================================
V2_DIR = _PROJECT_ROOT / "data" / "benchmark_v2"
V2_CACHE_DIR = V2_DIR / "cache"
V2_FIGURES_DIR = V2_DIR / "figures"
V2_LANDMARKS_SEED_CSV = V2_DIR / "landmarks_seed.csv"
V2_LANDMARKS_GEOCODED_CSV = V2_DIR / "landmarks_geocoded.csv"
V2_LANDMARKS_REVIEW_CSV = V2_DIR / "landmarks_review.csv"
V2_REVIEW_DECISIONS_CSV = V2_DIR / "review_decisions.csv"       # Gate-2 human decisions
V2_HOTSPOT_LEGS_GEOJSON = V2_DIR / "hotspot_legs.geojson"
V2_CANDIDATE_PAIRS_CSV = V2_DIR / "candidate_pairs.csv"
V2_OD_PAIRS_CSV = V2_DIR / "od_pairs.csv"
V2_OD_PAIRS_GEOJSON = V2_DIR / "od_pairs.geojson"
V2_REHEARSAL_DIR = V2_DIR / "rehearsal_approx"      # offline dry-run on approximate coords

# Existing Stage 2-4 inputs
RAW_GMAPS_DIR = _PROJECT_ROOT / "data" / "raw" / "gmaps_data"
FLATTENED_TRAFFIC_CSV = _PROJECT_ROOT / "output" / "flattened_traffic_data.csv"
OSM_GRAPH_PATH = _PROJECT_ROOT / "output" / "bangalore_drive.graphml"
UTM_CRS = "EPSG:32643"                                 # UTM zone 43N (metres)

# Bangalore rectangle for Places locationRestriction (≈ OSM graph extent + small margin)
V2_BBOX = {"low": {"latitude": 12.83, "longitude": 77.45},
           "high": {"latitude": 13.15, "longitude": 77.79}}

# --- Phase 1a: geocoding checks (METHODOLOGY §2) ---
PLACES_TEXT_SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"
PLACES_FIELD_MASK = ("places.id,places.displayName,places.formattedAddress,"
                     "places.location,places.types,places.primaryType")
GEOCODING_URL = "https://maps.googleapis.com/maps/api/geocode/json"
V2_PLACES_RESULTS = 5
V2_NAME_SCORE_MIN = 80          # token-set similarity, 0-100
V2_APPROX_MAX_M = 2000          # result must be within this of the approximate coordinate (or area match)
V2_AMBIGUITY_M = 1000           # another good name match farther than this → ambiguous
V2_SNAP_MAX_M = 150             # max distance to nearest drivable OSM edge
V2_AREA_TYPES = {"locality", "sublocality", "sublocality_level_1", "sublocality_level_2",
                 "political", "neighborhood", "postal_code", "administrative_area_level_1",
                 "administrative_area_level_2", "administrative_area_level_3", "country"}
V2_COMPACT_KINDS = {"metro_station", "junction"}
# Approximate Places Pro price for dry-run estimates (USD per call; free cap 5,000/month)
V2_PLACES_PRICE_PER_CALL = 0.032

# --- Phase 1b: pairs, tags, selection (METHODOLOGY §3-4) ---
V2_PAIR_MIN_STRAIGHT_M = 700
V2_PAIR_MAX_STRAIGHT_M = 22000
V2_BANDS = [("B1_1-5km", 1000, 5000), ("B2_5-12km", 5000, 12000), ("B3_12-25km", 12000, 25000)]
V2_SHORT_ROUTE_M = 2000                     # below this, both endpoints must be compact
V2_ARTERIAL_HIGHWAYS = {"motorway", "trunk", "primary",
                        "motorway_link", "trunk_link", "primary_link"}
V2_ARTERIAL_MIN_SHARE = 0.60
V2_SUBARTERIAL_MAX_SHARE = 0.40
V2_HOTSPOT_TOP_FRACTION = 0.20              # top 20% of plausible legs by CV of live duration
V2_HOTSPOT_BUFFER_M = 30
# Hotspot exposure = overlap share, split at the per-band median (D-17); no absolute threshold
V2_LEG_BBOX = (12.8, 13.25, 77.4, 77.85)    # lat_min, lat_max, lng_min, lng_max
V2_LEG_MAX_DETOUR = 2.0                     # leg distance / straight line
V2_LEG_MIN_SNAPSHOTS = 40
V2_TARGET_ROUTES = 72
V2_MAX_PER_GROUP = 6
V2_MAX_LANDMARK_USES = 3
V2_NEAR_DUP_M = 1500
