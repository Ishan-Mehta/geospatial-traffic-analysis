import pandas as pd
import requests
import time
import re
import json
import os
from dotenv import load_dotenv

load_dotenv()

# ==========================================
# CONFIGURATION
# ==========================================
API_KEY = os.getenv('GOOGLE_MAPS_API_KEY')

###############################################################################

INPUT_FILE = '../../data/raw/data_blr_roads_total.csv'
OUTPUT_FILE = '../../data/processed/geocoded_blr_roads_chain.csv'

# INPUT_FILE = './data/data_blr_arterial_roads.csv'
# OUTPUT_FILE = './data/geocoded_blr_arterial_roads_chain.csv'

# INPUT_FILE = './data/data_blr_sub_arterial_roads.csv'
# OUTPUT_FILE = './data/geocoded_blr_sub_arterial_roads_chain.csv'

###############################################################################


# Heuristic Settings (The "Blocklist")
BLOCKLIST = [
    "ORR", "Ring Road", "Outer Ring Road", 
    "BBMP Limit", "BBMP Limits", "BBMP",
    "BBMP Limits (Bidarahalli)", "BBMP Limit (Near NICE Road)",
    "Entrance", "Exit", "Start", "End"
]

# Words that make a location "Specific" even if it ends in "Road"
SPECIFIC_ANCHORS = [
    "Cross", "Junction", "Circle", "Near", "Opposite", "Opp", 
    "@", "Temple", "College", "School", "Layout", "Nagar", 
    "Block", "Stage", "Phase", "Colony", "Palya", "Gate", 
    "Factory", "Showroom", "Bunk", "Church", "Mosque"
]

# ==========================================
# 1. CORE HEURISTICS (Logic to clean data)
# ==========================================

def is_valid_location(text):
    """
    Decides if a text string is a specific enough location to be a coordinate anchor.
    Returns: True (Keep) or False (Discard)
    """
    if not isinstance(text, str) or not text.strip():
        return False
    
    clean_text = text.strip()
    
    # Rule 1: specific blocklist
    if clean_text in BLOCKLIST:
        return False
    
    # Rule 2: If it's just "X Road" or "Y Main Road" without a specific anchor, it's too vague.
    lower_text = clean_text.lower()
    is_generic_road = "road" in lower_text
    has_anchor = any(anchor.lower() in lower_text for anchor in SPECIFIC_ANCHORS)
    
    if is_generic_road and not has_anchor:
        return False

    return True

def parse_row_to_chain(row):
    """
    Extracts, merges, and cleans all location points from a DataFrame row.
    Returns a list of valid location strings: [Start, Waypoint1, ..., End]
    """
    raw_origin = str(row['Origin']) if pd.notna(row['Origin']) else ""
    raw_dest = str(row['Destination']) if pd.notna(row['Destination']) else ""
    raw_via = str(row['Enroute (Via)']) if pd.notna(row['Enroute (Via)']) else ""
    
    # 1. Split Via Points (Handle hyphens, commas, newlines)
    via_list = [x.strip() for x in re.split(r'[-,\n]', raw_via) if x.strip()]
    
    # 2. Merge into one sequence
    # Sequence: Origin -> [Via Points] -> Destination
    full_sequence = [raw_origin] + via_list + [raw_dest]
    
    # 3. Filter using Heuristics
    valid_chain = [loc for loc in full_sequence if is_valid_location(loc)]
    
    return valid_chain

# ==========================================
# 2. GEOCODING ENGINE (Using Requests)
# ==========================================

def fetch_coordinates_map(place_list, api_key):
    """
    Takes a list of place names, deduplicates them, and fetches coordinates.
    Returns a dictionary: {'Place Name': 'lat,lng'}
    """
    unique_places = set(place_list)
    coords_map = {}
    
    base_url = "https://maps.googleapis.com/maps/api/geocode/json"

    print(f"\n--- Starting Geocoding for {len(unique_places)} unique locations ---")
    
    for i, place in enumerate(unique_places):
        # Progress indicator
        if i % 5 == 0: print(f"Processing... ({i}/{len(unique_places)})")
        
        # Prepare parameters
        # We append ", Bangalore, India" to ensure the API searches in the right city
        params = {
            "address": f"{place}, Bangalore, India",
            "key": api_key
        }
        
        try:
            # The Requests Call
            response = requests.get(base_url, params=params)
            data = response.json()
            
            if data['status'] == 'OK':
                loc = data['results'][0]['geometry']['location']
                coords_map[place] = f"{loc['lat']},{loc['lng']}"
            else:
                print(f"⚠️ API returned {data['status']} for: {place}")
                coords_map[place] = None
                
        except Exception as e:
            print(f"❌ Network Error for {place}: {e}")
            coords_map[place] = None
        
        time.sleep(0.1) # Rate limit protection

    return coords_map

# ==========================================
# 3. MAIN PROCESSOR
# ==========================================

def process_roads(limit=None):
    # 1. Load Data
    print(f"Reading {INPUT_FILE}...")
    try:
        df = pd.read_csv(INPUT_FILE)
    except FileNotFoundError:
        print(f"❌ Error: {INPUT_FILE} not found. Please create the CSV first.")
        return

    # Filter for test mode
    if limit:
        print(f"Creating a TEST set of first {limit} rows.")
        df = df.head(limit).copy()

    # 2. Parse Chains (Logic Phase)
    print("Parsing text and building location chains...")
    df['Temp_Name_Chain'] = df.apply(parse_row_to_chain, axis=1)

    # 3. Collect Uniques (Optimization Phase)
    all_places = set()
    for chain in df['Temp_Name_Chain']:
        all_places.update(chain)
    
    # 4. Geocode (Network Phase)
    if not all_places:
        print("No valid places found to geocode! Check your CSV structure.")
        return

    coords_map = fetch_coordinates_map(list(all_places), API_KEY)
    
    # 5. Reconstruct Data (Assembly Phase)
    final_rows = []
    
    for index, row in df.iterrows():
        name_chain = row['Temp_Name_Chain']
        
        # Convert names to coordinates
        coord_chain = []
        valid_names_ordered = []
        
        for name in name_chain:
            c = coords_map.get(name)
            if c:
                coord_chain.append(c)
                valid_names_ordered.append(name)
        
        # Determine Status
        status = "OK"
        if len(coord_chain) < 2:
            status = "INCOMPLETE_CHAIN" # Warning flag
        
        # Build Result Row
        result_row = {
            "Zone": row.get('Zone', ''),
            "Sl_No": row.get('Sl No.', ''),
            "Road_Name": row.get('Name of the Road', ''),
            
            # Use 'Computed' points as your logic source of truth
            "Computed_Start_Point": valid_names_ordered[0] if valid_names_ordered else "N/A",
            "Computed_End_Point": valid_names_ordered[-1] if valid_names_ordered else "N/A",
            
            # This string is exactly what you need for the Traffic Scraper
            "Full_Coordinate_Chain": "|".join(coord_chain), 
            
            "Coordinate_Count": len(coord_chain),
            "Status": status,
            "Original_Via": row.get('Enroute (Via)', '')
        }
        final_rows.append(result_row)

    # 6. Save
    result_df = pd.DataFrame(final_rows)
    
    if 'Zone' in result_df.columns:
        result_df.sort_values(by=['Zone', 'Sl_No'], inplace=True)
        
    result_df.to_csv(OUTPUT_FILE, index=False)
    print("\n" + "="*40)
    print(f"DONE! Processed {len(df)} rows.")
    print(f"Results saved to: {OUTPUT_FILE}")
    print("="*40)

# ==========================================
# 4. USER MENU
# ==========================================

if __name__ == "__main__":
    print("=== Bangalore Traffic Road Geocoder (Requests Version) ===")
    print("1. Test Run (First 10 rows only)")
    print("2. Full Run (All rows)")
    
    choice = input("\nEnter your choice (1 or 2): ")
    
    if choice == '1':
        process_roads(limit=10)
    elif choice == '2':
        process_roads(limit=None)
    else:
        print("Invalid choice. Exiting.")