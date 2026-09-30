import os
import csv
import time
import requests
from pathlib import Path
from dotenv import load_dotenv

from config import BENCHMARK_ROUTES_CSV, BENCHMARK_ROUTES_GEOCODED_CSV

def get_best_name(address_components, formatted_address):
    sublocality = None
    neighborhood = None
    locality = None
    
    for comp in address_components:
        types = comp.get('types', [])
        if 'sublocality_level_1' in types:
            sublocality = comp.get('long_name')
        if 'neighborhood' in types:
            neighborhood = comp.get('long_name')
        if 'locality' in types:
            locality = comp.get('long_name')
            
    if sublocality:
        return sublocality
    if neighborhood:
        return neighborhood
    if locality:
        return locality
        
    # Fallback to formatted address
    parts = formatted_address.split(',')
    return ','.join(parts[:2]).strip()

def reverse_geocode(lat, lng, api_key):
    url = f"https://maps.googleapis.com/maps/api/geocode/json?latlng={lat},{lng}&key={api_key}"
    resp = requests.get(url)
    if resp.status_code != 200:
        return "Unknown Location"
    data = resp.json()
    if not data.get('results'):
        return "Unknown Location"
        
    best_result = data['results'][0]
    return get_best_name(best_result.get('address_components', []), best_result.get('formatted_address', 'Unknown Location'))

def main():
    env_path = Path(__file__).resolve().parent.parent.parent / '.env'
    load_dotenv(dotenv_path=env_path)
    
    api_key = os.getenv("GOOGLE_MAPS_API_KEY")
    if not api_key:
        print("Error: GOOGLE_MAPS_API_KEY not found in .env")
        return
        
    BENCHMARK_ROUTES_GEOCODED_CSV.parent.mkdir(parents=True, exist_ok=True)
    
    try:
        with open(BENCHMARK_ROUTES_CSV, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            fieldnames = reader.fieldnames + ['origin_name', 'destination_name']
    except FileNotFoundError:
        print(f"Error: {BENCHMARK_ROUTES_CSV} not found. Please ensure it exists.")
        return
        
    for i, row in enumerate(rows):
        start_lat, start_lng = row.get('start_lat'), row.get('start_lng')
        end_lat, end_lng = row.get('end_lat'), row.get('end_lng')
        
        print(f"[{i+1}/{len(rows)}] Geocoding route {row['sub_route_id']}...")
        
        row['origin_name'] = reverse_geocode(start_lat, start_lng, api_key)
        time.sleep(0.1)
        row['destination_name'] = reverse_geocode(end_lat, end_lng, api_key)
        time.sleep(0.1)
        
    with open(BENCHMARK_ROUTES_GEOCODED_CSV, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
        
    print(f"Saved geocoded routes to {BENCHMARK_ROUTES_GEOCODED_CSV}")

if __name__ == "__main__":
    main()
