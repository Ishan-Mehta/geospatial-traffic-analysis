"""
End-to-end test script for the LLM benchmark pipeline.
Tests a single route and single time slot to verify the whole flow works.
"""

import json
import os
import time
from pathlib import Path
import pandas as pd
import requests
from dotenv import load_dotenv

# Set up paths
_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _DIR.parent.parent
ENV_PATH = _PROJECT_ROOT / ".env"
BENCHMARK_DIR = _PROJECT_ROOT / "data" / "benchmark"
BENCHMARK_ROUTES_CSV = BENCHMARK_DIR / "benchmark_routes.csv"
TEST_OUT_DIR = BENCHMARK_DIR / "test"

# Make sure output directory exists
TEST_OUT_DIR.mkdir(parents=True, exist_ok=True)

# Load env variables
load_dotenv(dotenv_path=ENV_PATH)

from google import genai
from google.genai import types

def main():
    print("=== Starting LLM Benchmark E2E Test ===")
    
    # ---------------------------------------------------------
    # 1. Load Route
    # ---------------------------------------------------------
    if not BENCHMARK_ROUTES_CSV.exists():
        print(f"FAIL: Could not find benchmark routes at {BENCHMARK_ROUTES_CSV}")
        return
        
    df = pd.read_csv(BENCHMARK_ROUTES_CSV)
    if df.empty:
        print("FAIL: benchmark_routes.csv is empty")
        return
        
    # Get just 1 route
    route = df.iloc[0].to_dict()
    route_id = route["sub_route_id"]
    print(f"\n[1] Picked Test Route: {route_id} ({route['road_name']})")
    
    # ---------------------------------------------------------
    # 2. Geocoding Test (Mocked or real)
    # ---------------------------------------------------------
    gmaps_api_key = os.environ.get("GOOGLE_MAPS_API_KEY")
    if not gmaps_api_key:
        print("FAIL: GOOGLE_MAPS_API_KEY not found in env")
        return
        
    print("\n[2] Testing Reverse Geocoding...")
    url = f"https://maps.googleapis.com/maps/api/geocode/json?latlng={route['start_lat']},{route['start_lng']}&key={gmaps_api_key}"
    resp = requests.get(url)
    
    start_addr = f"{route['start_lat']},{route['start_lng']}"
    if resp.status_code == 200:
        data = resp.json()
        if data.get("results"):
            start_addr = data["results"][0].get("formatted_address", start_addr)
            print(f"  Start Address: {start_addr}")
        else:
            print("  Geocode returned empty results.")
    else:
        print(f"  Geocode API failed with status {resp.status_code}")
        
    url_end = f"https://maps.googleapis.com/maps/api/geocode/json?latlng={route['end_lat']},{route['end_lng']}&key={gmaps_api_key}"
    resp_end = requests.get(url_end)
    end_addr = f"{route['end_lat']},{route['end_lng']}"
    if resp_end.status_code == 200:
        data = resp_end.json()
        if data.get("results"):
            end_addr = data["results"][0].get("formatted_address", end_addr)
            print(f"  End Address: {end_addr}")
            
    # Write tiny CSV
    test_csv = TEST_OUT_DIR / "test_geocode.csv"
    pd.DataFrame([route]).to_csv(test_csv, index=False)
    print(f"  Saved mini CSV to {test_csv}")
            
    # ---------------------------------------------------------
    # 3. LLM Query Test
    # ---------------------------------------------------------
    print("\n[3] Testing LLM Query (Gemini)...")
    gemini_key = os.environ.get("GEMINI_API_KEY")
    if not gemini_key:
        print("FAIL: GEMINI_API_KEY not found in env")
        return
        
    client = genai.Client(api_key=gemini_key)
    
    ROUTE_SCHEMA = {
        'type': 'OBJECT',
        'required': ['suggested_route', 'estimated_distance_km', 'estimated_time_minutes', 'traffic_awareness', 'reasoning'],
        'properties': {
            'suggested_route': {'type': 'ARRAY', 'items': {'type': 'STRING'}},
            'estimated_distance_km': {'type': 'NUMBER'},
            'estimated_time_minutes': {'type': 'NUMBER'},
            'traffic_awareness': {'type': 'STRING', 'enum': ['none', 'light', 'moderate', 'heavy']},
            'reasoning': {'type': 'STRING'},
        },
    }
    
    system_prompt_text = (
        "You are a routing assistant for car travel in Bangalore, India.\n\n"
        "IMPORTANT CONSTRAINTS:\n"
        "- Do NOT use any external tool, mapping service, Google Maps, navigation agent, or real-time data source.\n"
        "- Answer based ONLY on your general knowledge of Bangalore's road network and traffic patterns.\n"
        "- You MUST provide numeric estimates even if uncertain. Do not refuse or say you cannot determine this.\n"
        "- Consider the time of day and day of week when estimating travel time."
    )
    
    user_prompt = f"Estimate the route, distance, and time from {start_addr} to {end_addr} at 14:00 on a WEEKDAY."
    print(f"  Prompt: {user_prompt}")
    
    try:
        response = client.models.generate_content(
            model='gemini-3.5-flash',
            contents=user_prompt,
            config=types.GenerateContentConfig(
                response_mime_type='application/json',
                response_json_schema=ROUTE_SCHEMA,
                system_instruction=system_prompt_text,
            ),
        )
        
        llm_result = json.loads(response.text)
        print(f"  LLM Result: {llm_result}")
        
        llm_out_file = TEST_OUT_DIR / "llm_test.json"
        with open(llm_out_file, "w") as f:
            json.dump(llm_result, f, indent=2)
        print(f"  Saved to {llm_out_file}")
    except Exception as e:
        print(f"FAIL: LLM Query failed: {e}")
        return

    # ---------------------------------------------------------
    # 4. GMaps Query Test
    # ---------------------------------------------------------
    print("\n[4] Testing Google Maps Query...")
    
    gmaps_url = "https://routes.googleapis.com/directions/v2:computeRoutes"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": gmaps_api_key,
        "X-Goog-FieldMask": "routes.duration,routes.distanceMeters,routes.staticDuration"
    }
    
    payload = {
        "origin": {
            "location": {
                "latLng": {
                    "latitude": route["start_lat"],
                    "longitude": route["start_lng"]
                }
            }
        },
        "destination": {
            "location": {
                "latLng": {
                    "latitude": route["end_lat"],
                    "longitude": route["end_lng"]
                }
            }
        },
        "travelMode": "DRIVE",
        "routingPreference": "TRAFFIC_AWARE"
    }
    
    try:
        g_resp = requests.post(gmaps_url, headers=headers, json=payload)
        if g_resp.status_code == 200:
            gmaps_result = g_resp.json()
            print(f"  GMaps Result: {gmaps_result}")
            
            gmaps_out_file = TEST_OUT_DIR / "gmaps_test.json"
            with open(gmaps_out_file, "w") as f:
                json.dump(gmaps_result, f, indent=2)
            print(f"  Saved to {gmaps_out_file}")
        else:
            print(f"FAIL: GMaps API failed: {g_resp.text}")
            return
    except Exception as e:
        print(f"FAIL: GMaps request failed: {e}")
        return

    # ---------------------------------------------------------
    # 5. Compare Test
    # ---------------------------------------------------------
    print("\n[5] Testing Comparison Logic...")
    try:
        # LLM distance & time
        llm_dist_m = llm_result.get("estimated_distance_km", 0) * 1000
        llm_time_s = llm_result.get("estimated_time_minutes", 0) * 60
        
        # GMaps distance & time
        route_data = gmaps_result.get("routes", [{}])[0]
        g_dist_m = route_data.get("distanceMeters", 0)
        g_time_str = route_data.get("duration", "0s")
        g_time_s = int(g_time_str.replace("s", "")) if g_time_str.endswith("s") else 0
        
        print("  --- Comparison ---")
        print(f"  Distance: LLM={llm_dist_m/1000:.2f}km | GMaps={g_dist_m/1000:.2f}km")
        print(f"  Time:     LLM={llm_time_s/60:.2f}m   | GMaps={g_time_s/60:.2f}m")
        
        if g_dist_m > 0:
            dist_err = abs(llm_dist_m - g_dist_m) / g_dist_m * 100
            print(f"  Distance Error: {dist_err:.2f}%")
        if g_time_s > 0:
            time_err = abs(llm_time_s - g_time_s) / g_time_s * 100
            print(f"  Time Error: {time_err:.2f}%")
            
    except Exception as e:
        print(f"FAIL: Comparison failed: {e}")
        return
        
    print("\n=== PIPELINE TEST PASSED ===")

if __name__ == "__main__":
    main()
