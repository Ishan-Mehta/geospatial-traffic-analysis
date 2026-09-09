import os
import json
import glob
import hashlib
import csv
import time

# ==========================================
# CONFIGURATION - CHANGE THESE PATHS
# ==========================================
# Update this variable to point to the folder containing your 84 JSON files.
# Example: '/Users/yourname/Documents/traffic_data_scrapes'
INPUT_JSON_DIR = '../../data/raw/gmaps_data/' 

# These are the output file names. You can change the paths if you want them 
# saved in a specific output directory.
MASTER_SUBROUTES_CSV = '../../output/master_subroutes.csv'
FLATTENED_TRAFFIC_CSV = '../../output/flattened_traffic_data.csv'

# 4 decimal places = ~11 meters of precision. 
# You can change this to 3 (~110m) if you want broader grouping, 
# or 5 (~1.1m) for stricter matching.
COORD_PRECISION = 4 

# Number of records to hold in RAM before writing to the flattened CSV.
# 10,000 is a good balance between memory usage and disk I/O efficiency.
WRITE_BATCH_SIZE = 10000
# ==========================================


def yield_routes_from_directory(input_dir):
    """
    Generator function to iterate through a directory of JSON files.
    It reads one file at a time, yields individual route records, and 
    prevents the entire 6.7GB dataset from loading into RAM.
    """
    # Find all JSON files in the specified directory
    search_pattern = os.path.join(input_dir, '*.json')
    json_files = glob.glob(search_pattern)
    
    if not json_files:
        print(f"Warning: No JSON files found in directory: {input_dir}")
        return

    print(f"Found {len(json_files)} JSON files. Beginning extraction...")

    for file_path in json_files:
        print(f"Processing file: {os.path.basename(file_path)}...")
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
                # The data is a list of dictionaries, each representing a road's snapshot
                for snapshot in data:
                    road_name = snapshot.get('road_name', 'Unknown')
                    timestamp = snapshot.get('request_timestamp', 'Unknown')
                    
                    # Safely navigate the nested JSON structure to get the routes
                    api_response = snapshot.get('api_response', {})
                    routes = api_response.get('routes', [])
                    
                    for route in routes:
                        # Yield bundles the data and pauses the function until the 
                        # next item is requested by our main loop (which we will build later).
                        yield {
                            'road_name': road_name,
                            'timestamp': timestamp,
                            'route_data': route
                        }
                        
        except Exception as e:
            print(f"Error processing {os.path.basename(file_path)}: {e}")


def generate_sub_route_id(start_lat, start_lng, end_lat, end_lng):
    """
    Creates a unique, deterministic ID for a route leg based on its start and 
    end coordinates. Uses rounding for spatial tolerance and MD5 for a clean hash.
    """
    # 1. Round coordinates to group highly similar points together
    slat = round(float(start_lat), COORD_PRECISION)
    slng = round(float(start_lng), COORD_PRECISION)
    elat = round(float(end_lat), COORD_PRECISION)
    elng = round(float(end_lng), COORD_PRECISION)
    
    # 2. Create a standardized string representation
    coord_string = f"{slat}_{slng}_{elat}_{elng}"
    
    # 3. Hash the string to create a uniform 32-character hex ID
    # MD5 is perfectly fine here as we don't need cryptographic security, 
    # just a fast, unique identifier.
    leg_hash = hashlib.md5(coord_string.encode('utf-8')).hexdigest()
    
    return f"leg_{leg_hash}"

# Dictionary to hold our distinct master sub-routes in RAM.
# Key: sub_route_id, Value: Dictionary of leg details
master_subroutes_dict = {}

def process_route_legs(route_record):
    """
    Takes a single yielded route record, extracts the LEGS as distinct sub-routes, 
    and perfectly maps live and static durations.
    """
    flattened_records = []
    
    road_name = route_record['road_name']
    timestamp = route_record['timestamp']
    route_data = route_record['route_data']
    
    legs = route_data.get('legs', [])
    
    for leg in legs:
        # 1. Extract coordinates directly from the GeoJSON polyline array
        # The array contains the full path. We just need the first and last point.
        polyline_coords = leg.get('polyline', {}).get('geoJsonLinestring', {}).get('coordinates', [])
        
        # Skip if the polyline is missing or invalid
        if not polyline_coords or len(polyline_coords) < 2:
            continue 
            
        start_coord = polyline_coords[0]
        end_coord = polyline_coords[-1]
        
        # GeoJSON strictly formats as [Longitude, Latitude]
        start_lng, start_lat = start_coord[0], start_coord[1]
        end_lng, end_lat = end_coord[0], end_coord[1]
        
        # 2. Generate our unique ID based on the Leg's start/end
        sub_route_id = generate_sub_route_id(start_lat, start_lng, end_lat, end_lng)
        
        # 3. Extract the clean durations! No more multipliers needed!
        raw_live = leg.get('duration', '0s')
        raw_static = leg.get('staticDuration', '0s')
        
        live_duration_s = int(raw_live.replace('s', '')) if raw_live else 0
        static_duration_s = int(raw_static.replace('s', '')) if raw_static else 0
        
        distance_m = leg.get('distanceMeters', 0)
        
        # 4. Populate the Master Dictionary
        if sub_route_id not in master_subroutes_dict:
            master_subroutes_dict[sub_route_id] = {
                'sub_route_id': sub_route_id,
                'start_lat': start_lat, 
                'start_lng': start_lng,
                'end_lat': end_lat,
                'end_lng': end_lng,
                'distance_meters': distance_m,
                'static_duration_s': static_duration_s 
            }
        
        # 5. Populate the Flattened Traffic Dataset
        flattened_records.append({
            'timestamp': timestamp,
            'road_name': road_name,
            'sub_route_id': sub_route_id,
            'live_duration_s': live_duration_s, 
            'static_duration_s': static_duration_s
        })
            
    return flattened_records

def run_pipeline():
    """
    The main execution loop. Orchestrates reading, processing, batching, 
    and writing the data to disk.
    """
    print(f"Starting data pipeline...")
    start_time = time.time()
    
    # Trackers for our final summary
    total_routes_processed = 0
    total_legs_processed = 0
    
    # Buffer for batch writing
    records_buffer = []
    
    # 1. Prepare the flattened CSV file with headers
    flattened_headers = [
        'timestamp', 'road_name', 'sub_route_id', 'live_duration_s', 'static_duration_s'
    ]
    
    # Open in 'w' mode initially to create the file and write headers.
    with open(FLATTENED_TRAFFIC_CSV, 'w', newline='', encoding='utf-8') as f_csv:
        writer = csv.DictWriter(f_csv, fieldnames=flattened_headers)
        writer.writeheader()
        
    print(f"Created {FLATTENED_TRAFFIC_CSV} and wrote headers.")

    # 2. Open the file in append mode ('a') for the processing loop
    with open(FLATTENED_TRAFFIC_CSV, 'a', newline='', encoding='utf-8') as f_csv:
        writer = csv.DictWriter(f_csv, fieldnames=flattened_headers)
        
        # Pull one route at a time from our generator
        for route_record in yield_routes_from_directory(INPUT_JSON_DIR):
            total_routes_processed += 1
            
            # Process the nested legs/steps
            flattened_records = process_route_legs(route_record)
            
            if flattened_records:
                records_buffer.extend(flattened_records)
                total_legs_processed += len(flattened_records)
            
            # 3. Batch write to disk when the buffer is full
            if len(records_buffer) >= WRITE_BATCH_SIZE:
                writer.writerows(records_buffer)
                records_buffer.clear() # Empty the buffer to free up RAM
                
        # 4. Write any remaining records in the buffer after the loop finishes
        if records_buffer:
            writer.writerows(records_buffer)
            records_buffer.clear()

    # 5. Write the Master Sub-routes to disk
    print(f"Writing master sub-routes to {MASTER_SUBROUTES_CSV}...")
    master_headers = [
        'sub_route_id', 'start_lat', 'start_lng', 'end_lat', 'end_lng', 
        'distance_meters', 'static_duration_s'
    ]
    
    with open(MASTER_SUBROUTES_CSV, 'w', newline='', encoding='utf-8') as m_csv:
        writer = csv.DictWriter(m_csv, fieldnames=master_headers)
        writer.writeheader()
        # master_subroutes_dict.values() gives us the dictionaries we stored earlier
        writer.writerows(master_subroutes_dict.values())

    # 6. Print Summary Statistics
    elapsed_time = time.time() - start_time
    print("\n" + "="*40)
    print("PIPELINE EXECUTION SUMMARY")
    print("="*40)
    print(f"Total Routes Processed:      {total_routes_processed:,}")
    print(f"Total Legs/Steps Processed:  {total_legs_processed:,}")
    print(f"Distinct Sub-routes Found:   {len(master_subroutes_dict):,}")
    print(f"Total Execution Time:        {elapsed_time:.2f} seconds")
    print("="*40)

# Entry point for the script
if __name__ == "__main__":
    # Make sure your INPUT_JSON_DIR is set correctly at the top of the file!
    run_pipeline()