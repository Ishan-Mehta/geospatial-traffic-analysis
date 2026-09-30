import os
import json
import time
import datetime
from zoneinfo import ZoneInfo
import requests
import csv
from pathlib import Path
from dotenv import load_dotenv

from config import (
    BENCHMARK_ROUTES_GEOCODED_CSV,
    TIME_SLOTS,
    DAY_TYPES,
    GMAPS_RESPONSES_DIR,
    GMAPS_ROUTES_URL,
    GMAPS_FIELD_MASK,
    GMAPS_API_KEY_ENV
)

def get_next_occurrence(day_type, time_str):
    # IST timezone
    ist = ZoneInfo("Asia/Kolkata")
    now = datetime.datetime.now(ist)
    
    # Target weekday: WEDNESDAY (2) for WEEKDAY, SATURDAY (5) for WEEKEND
    target_weekday = 2 if day_type == "WEEKDAY" else 5
    
    # Parse target time
    t_hour, t_min = map(int, time_str.split(':'))
    
    # Find next occurrence
    days_ahead = target_weekday - now.weekday()
    if days_ahead <= 0: # Target day already happened this week
        days_ahead += 7
        
    next_date = now + datetime.timedelta(days=days_ahead)
    target_dt = next_date.replace(hour=t_hour, minute=t_min, second=0, microsecond=0)
    
    # If the computed time is still in the past (e.g., today is target day but time passed)
    if target_dt < now:
        target_dt += datetime.timedelta(days=7)
        
    # Convert to UTC ISO 8601
    target_dt_utc = target_dt.astimezone(datetime.timezone.utc)
    return target_dt_utc.strftime("%Y-%m-%dT%H:%M:%SZ")

def main():
    print("Starting GMaps queries...")
    env_path = Path(__file__).resolve().parent.parent.parent / '.env'
    load_dotenv(dotenv_path=env_path)
    
    api_key = os.environ.get(GMAPS_API_KEY_ENV)
    if not api_key:
        print(f"Error: {GMAPS_API_KEY_ENV} not found in .env")
        return
        
    GMAPS_RESPONSES_DIR.mkdir(parents=True, exist_ok=True)
    
    # Read geocoded routes
    routes = []
    with open(BENCHMARK_ROUTES_GEOCODED_CSV, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            routes.append(row)
            
    headers = {
        'Content-Type': 'application/json',
        'X-Goog-Api-Key': api_key,
        'X-Goog-FieldMask': GMAPS_FIELD_MASK
    }
    
    results = []
    
    for route in routes:
        sub_route_id = route.get('sub_route_id')
        start_lat = float(route.get('start_lat'))
        start_lng = float(route.get('start_lng'))
        end_lat = float(route.get('end_lat'))
        end_lng = float(route.get('end_lng'))
        
        for slot in TIME_SLOTS:
            time_slot_id = slot['id']
            time_str = slot['time']
            
            for day_type in DAY_TYPES:
                departure_time_iso = get_next_occurrence(day_type, time_str)
                
                payload = {
                    'origin': {'location': {'latLng': {'latitude': start_lat, 'longitude': start_lng}}},
                    'destination': {'location': {'latLng': {'latitude': end_lat, 'longitude': end_lng}}},
                    'travelMode': 'DRIVE',
                    'routingPreference': 'TRAFFIC_AWARE',
                    'departureTime': departure_time_iso,
                }
                
                print(f"Querying sub_route: {sub_route_id}, time_slot: {time_slot_id}, day_type: {day_type}")
                
                try:
                    resp = requests.post(GMAPS_ROUTES_URL, headers=headers, json=payload)
                    resp.raise_for_status()
                    data = resp.json()
                    
                    routes_data = data.get('routes', [])
                    if not routes_data:
                        print(f"  No routes found for {sub_route_id}")
                        continue
                        
                    route_info = routes_data[0]
                    dist_m = int(route_info.get('distanceMeters', 0))
                    duration_s = int(route_info.get('duration', '0s').rstrip('s'))
                    static_duration_s = int(route_info.get('staticDuration', '0s').rstrip('s'))
                    desc = route_info.get('description', '')
                    
                    # Count traffic segments
                    segments = {'NORMAL': 0, 'SLOW': 0, 'TRAFFIC_JAM': 0}
                    advisory = route_info.get('travelAdvisory', {})
                    for interval in advisory.get('speedReadingIntervals', []):
                        speed = interval.get('speed')
                        if speed in segments:
                            segments[speed] += 1
                            
                    results.append({
                        'sub_route_id': sub_route_id,
                        'time_slot': time_slot_id,
                        'day_type': day_type,
                        'departure_time': departure_time_iso,
                        'distance_m': dist_m,
                        'live_duration_s': duration_s,
                        'static_duration_s': static_duration_s,
                        'delay_s': max(0, duration_s - static_duration_s),
                        'route_description': desc,
                        'traffic_segments': segments,
                        'query_timestamp': datetime.datetime.now(datetime.timezone.utc).isoformat()
                    })
                    
                except Exception as e:
                    print(f"  Error: {e}")
                
                time.sleep(0.1)
                
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    out_file = GMAPS_RESPONSES_DIR / f"gmaps_live_{timestamp}.json"
    with open(out_file, 'w') as f:
        json.dump(results, f, indent=2)
        
    print(f"Saved {len(results)} results to {out_file}")

if __name__ == "__main__":
    main()
