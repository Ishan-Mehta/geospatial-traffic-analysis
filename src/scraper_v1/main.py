import pandas as pd
import requests
import json
import time
import os
from dotenv import load_dotenv
from datetime import datetime, timezone

# ================= CONFIGURATION =================
load_dotenv()

API_KEY = os.getenv('GOOGLE-MAPS-API-KEY')  # Replace with your actual key
INPUT_CSV = "../../data/processed/geocoded_optimised_blr_roads.csv"

# Folder Setup
DATA_DIR = "../../data/raw"


# API Endpoint
URL = "https://routes.googleapis.com/directions/v2:computeRoutes"

FIELD_MASK = "routes.duration,routes.staticDuration,routes.distanceMeters,routes.polyline,routes.travelAdvisory,routes.description,routes.legs.duration,routes.legs.staticDuration,routes.legs.distanceMeters,routes.legs.polyline,routes.legs.steps.staticDuration,routes.legs.steps.distanceMeters,routes.legs.steps.navigationInstruction,routes.legs.travelAdvisory.speedReadingIntervals"

def construct_payload(coordinate_chain):
    """
    Parses the coordinate string and builds the API payload.
    """
    raw_coords = coordinate_chain.split('|')
    
    if len(raw_coords) < 2:
        return None 

    # Origin (First)
    lat_o, lng_o = raw_coords[0].split(',')
    origin = {
        "location": {"latLng": {"latitude": float(lat_o), "longitude": float(lng_o)}}
    }

    # Destination (Last)
    lat_d, lng_d = raw_coords[-1].split(',')
    destination = {
        "location": {"latLng": {"latitude": float(lat_d), "longitude": float(lng_d)}}
    }

    # Intermediates (Middle points)
    intermediates = []
    for coord in raw_coords[1:-1]:
        lat, lng = coord.split(',')
        intermediates.append({
            "via": False, 
            "location": {"latLng": {"latitude": float(lat), "longitude": float(lng)}}
        })

    payload = {
        "origin": origin,
        "destination": destination,
        "intermediates": intermediates,
        "travelMode": "DRIVE",
        "routingPreference": "TRAFFIC_AWARE",
        # "departureTime": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "computeAlternativeRoutes": False,
        "polylineEncoding": "GEO_JSON_LINESTRING",
        "extraComputations": ["TRAFFIC_ON_POLYLINE"],
        "languageCode": "en-US"
    }
    
    return payload

def process_traffic_intervals(intervals):
    """
    Summarizes traffic jams into counts for the CSV.
    """
    summary = {"NORMAL": 0, "SLOW": 0, "TRAFFIC_JAM": 0}
    if not intervals:
        return summary
    for interval in intervals:
        traffic_state = interval.get("speed", "NORMAL")
        if traffic_state in summary:
            summary[traffic_state] += 1
    return summary

def main():
    
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
    
    # 1. Setup Timestamps for filenames
    run_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_filename = f"{DATA_DIR}/bangalore_traffic_summary_{run_timestamp}.csv"
    json_filename = f"{DATA_DIR}/bangalore_routes_response_{run_timestamp}.json"

    # 2. Load road data & Check for Trial Mode
    try:
        df = pd.read_csv(INPUT_CSV)
        
        # === NEW CODE STARTS HERE ===
        # print(f"Loaded {len(df)} total routes.")
        # trial_mode = input("Run a TRIAL for just 10 routes? (y/n): ").strip().lower()
        
        # if trial_mode == 'y':
        #     print("🧪 TRIAL MODE ON: Slicing dataset to first 10 routes only.")
        #     df = df.head(10)
        # === NEW CODE ENDS HERE ===

    except FileNotFoundError:
        print(f"❌ Error: Could not find {INPUT_CSV}")
        return

    summary_results = []

    summary_results = [] # To be saved as CSV
    raw_responses = []   # To be saved as JSON
    
    print(f"Starting traffic fetch for {len(df)} roads at {run_timestamp}...")

    # 3. Loop through roads
    for index, row in df.iterrows():
        road_name = row.get('Road_Name', f"Road_{index}")
        coord_chain = row['Full_Coordinate_Chain']
        
        payload = construct_payload(coord_chain)
        if not payload:
            print(f"!! Skipping {road_name} (Invalid Coordinates)")
            continue

        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": API_KEY,
            "X-Goog-FieldMask": FIELD_MASK
        }
        
        try:
            # === API CALL ===
            response = requests.post(URL, json=payload, headers=headers)
            
            if response.status_code == 200:
                data = response.json()
                
                # --- A. STORE RAW DATA ---
                # We wrap the raw response with metadata so you know which road it belongs to
                raw_entry = {
                    "road_name": road_name,
                    "request_timestamp": datetime.now(timezone.utc).isoformat(),
                    "api_response": data
                }
                raw_responses.append(raw_entry)

                # --- B. PROCESS SUMMARY DATA ---
                if "routes" in data and len(data["routes"]) > 0:
                    route = data["routes"][0]
                    
                    # 1. LIVE Traffic Time
                    duration_seconds = int(route.get("duration", "0s").rstrip("s"))
                    
                    # 2. BASELINE (No Traffic) Time
                    static_seconds = int(route.get("staticDuration", "0s").rstrip("s"))
                    if static_seconds == 0: 
                        static_seconds = duration_seconds

                    # 3. Calculate Delay
                    traffic_delay_seconds = duration_seconds - static_seconds
                    
                    # 4. Get Google's Description (NEW)
                    google_description = route.get("description", "No Description")

                    distance_meters = route.get("distanceMeters", 0)
                    travel_advisory = route.get("travelAdvisory", {})
                    traffic_summary = process_traffic_intervals(travel_advisory.get("speedReadingIntervals", []))

                    # LEG BREAKDOWN
                    legs_data = []
                    for i, leg in enumerate(route.get("legs", [])):
                        leg_duration = int(leg.get("duration", "0s").rstrip("s"))
                        leg_static = int(leg.get("staticDuration", "0s").rstrip("s"))
                        
                        # Extract traffic intervals for this specific leg
                        leg_advisory = leg.get("travelAdvisory", {})
                        leg_traffic = process_traffic_intervals(leg_advisory.get("speedReadingIntervals", []))
                        
                        legs_data.append({
                            f"Leg_{i+1}_Live": leg_duration,
                            f"Leg_{i+1}_Static": leg_static,
                            f"Leg_{i+1}_Jam_Segments": leg_traffic["TRAFFIC_JAM"]
                        })

                    summary_results.append({
                        "Road_Name": road_name,
                        "Google_Description": google_description, # <--- Added here
                        "Timestamp_UTC": datetime.now(timezone.utc).isoformat(),
                        "Duration_Live_Seconds": duration_seconds,
                        "Duration_Static_Seconds": static_seconds,
                        "Traffic_Delay_Seconds": traffic_delay_seconds,
                        "Distance_Meters": distance_meters,
                        "Traffic_Normal_Segments": traffic_summary["NORMAL"],
                        "Traffic_Slow_Segments": traffic_summary["SLOW"],
                        "Traffic_Jam_Segments": traffic_summary["TRAFFIC_JAM"],
                        "Leg Details": json.dumps(legs_data)
                    })
                    
                    # Updated print statement to show the description
                    print(f"✅ {road_name} ({google_description}): {duration_seconds}s | Delay: {traffic_delay_seconds}s")
                else:
                    print(f"⚠️ No route found for {road_name}")
            else:
                print(f"❌ API Error {response.status_code}: {response.text}")
                # Even on error, you might want to log the raw error response
                raw_responses.append({
                    "road_name": road_name,
                    "error": response.text,
                    "status_code": response.status_code
                })
                
        except Exception as e:
            print(f"❌ Request Failed for {road_name}: {e}")

        # Optional: Sleep slightly to avoid hitting rate limits instantly
        # time.sleep(0.05) 

    # 4. Save Summary CSV
    if summary_results:
        output_df = pd.DataFrame(summary_results)
        output_df.to_csv(csv_filename, index=False)
        print(f"\nSummary data saved to: {csv_filename}")
    
    # 5. Save Raw JSON
    if raw_responses:
        with open(json_filename, 'w', encoding='utf-8') as f:
            json.dump(raw_responses, f, indent=4, ensure_ascii=False)
        print(f"Raw JSON response saved to: {json_filename}")

    print(f"Batch processing complete for {run_timestamp}.")

if __name__ == "__main__":
    print("🤖 Traffic Bot Initialized. Press Ctrl+C to stop.")
    while True:
        try:
            time_before = datetime.now()
            main()
            time_after = datetime.now()
            print("💤 Sleeping for 2 hours...")
            # break
        except Exception as e:
            print(f"❌ Critical Error: {e}")

        # Sleep for 2 hours
        time.sleep(7200 - (time_after - time_before).total_seconds())