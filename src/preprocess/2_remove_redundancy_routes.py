import pandas as pd
import ast

INPUT_FILE = '../../data/processed/geocoded_blr_roads_chain.csv'
OUTPUT_FILE = '../../data/processed/geocoded_optimised_blr_roads.csv'


# Precision: 4 decimal places is roughly 11 meters.
# This groups points that are practically the same intersection.
ROUNDING_PRECISION = 4 

def round_point(coord_str):
    """
    Parses "12.12345,77.12345" -> "12.1235,77.1235"
    """
    try:
        lat, lng = map(float, coord_str.split(','))
        return f"{round(lat, ROUNDING_PRECISION)},{round(lng, ROUNDING_PRECISION)}"
    except:
        return None

def get_rounded_chain(chain_str):
    if pd.isna(chain_str): return []
    points = chain_str.split('|')
    return [round_point(p) for p in points if round_point(p)]

def is_subsequence(small_chain, big_chain):
    """
    Checks if small_chain is a continuous subset of big_chain.
    e.g. [B, C] is inside [A, B, C, D] -> True
    e.g. [A, C] is inside [A, B, C, D] -> False (skipped B)
    """
    if len(small_chain) > len(big_chain) or len(small_chain) == 0:
        return False
    
    # Sliding window check
    for i in range(len(big_chain) - len(small_chain) + 1):
        if big_chain[i : i + len(small_chain)] == small_chain:
            return True
    return False

# ==========================================
# MAIN EXECUTION
# ==========================================

print(f"Reading {INPUT_FILE}...")
df = pd.read_csv(INPUT_FILE)
original_count = len(df)

# 1. FILTER: Remove Incomplete Chains
print("Step 1: Removing INCOMPLETE_CHAIN rows...")
df = df[df['Status'] != 'INCOMPLETE_CHAIN'].copy()
after_filter_count = len(df)
print(f"   -> Removed {original_count - after_filter_count} incomplete rows.")

# 2. PREPARE: Normalize Coordinates
print("Step 2: Normalizing coordinates (rounding)...")
df['rounded_chain'] = df['Full_Coordinate_Chain'].apply(get_rounded_chain)
df['start_point'] = df['rounded_chain'].apply(lambda x: x[0] if x else None)
df['end_point'] = df['rounded_chain'].apply(lambda x: x[-1] if x else None)
df['points_count'] = df['rounded_chain'].apply(len)

# 3. LOGIC A: The "Richness" Heuristic
# If two routes have the EXACT same Start and End points, 
# keep ONLY the one with the most via-points (the longest chain).
print("Step 3: Removing 'Low Detail' duplicates (Richness Heuristic)...")
# Sort by points_count descending so the "richest" route is first
df.sort_values(by='points_count', ascending=False, inplace=True)

# Drop duplicates based on Start+End, keeping the first (which is now the longest)
# Note: We keep "Sl_No" to track what we kept
df_rich = df.drop_duplicates(subset=['start_point', 'end_point'], keep='first').copy()

removed_richness = len(df) - len(df_rich)
print(f"   -> Dropped {removed_richness} generic routes (e.g., kept 'A->Via->B', dropped 'A->B').")

# 4. LOGIC B: The "Subset" Deduplication
# Check if any remaining route is just a segment of a longer route
print("Step 4: Removing Subset Routes (Overlap check)...")

# We work with the remaining dataset
rows = df_rich.to_dict('records')
ids_to_drop = set()

# Sort by length descending again to optimize comparisons
rows.sort(key=lambda x: x['points_count'], reverse=True)

for i in range(len(rows)):
    current_id = rows[i]['Sl_No']
    current_chain = rows[i]['rounded_chain']
    
    # Compare against every other route
    # Optimization: We only need to check if 'current' is inside 'larger'
    # Since we sorted by length, 'larger' routes are at indices 0 to i-1
    for j in range(i):
        larger_chain = rows[j]['rounded_chain']
        
        # We only care if the larger chain is actually longer
        if len(larger_chain) > len(current_chain):
            if is_subsequence(current_chain, larger_chain):
                # We found a parent! Current row is redundant.
                ids_to_drop.add(current_id)
                break

df_final = df_rich[~df_rich['Sl_No'].isin(ids_to_drop)].copy()

removed_subset = len(df_rich) - len(df_final)
print(f"   -> Dropped {removed_subset} subset routes (routes fully contained inside others).")

# 5. CLEANUP & SAVE
columns_to_save = [
    'Zone', 'Sl_No', 'Road_Name', 'Computed_Start_Point', 
    'Computed_End_Point', 'Full_Coordinate_Chain', 'Coordinate_Count'
]
# Ensure columns exist (in case input CSV varied)
valid_cols = [c for c in columns_to_save if c in df_final.columns]
df_final = df_final[valid_cols]

# Sort for neatness
if 'Zone' in df_final.columns:
    df_final.sort_values(by=['Zone', 'Sl_No'], inplace=True)

df_final.to_csv(OUTPUT_FILE, index=False)

print("\n" + "="*40)
print(f"OPTIMIZATION COMPLETE")
print(f"Original Routes:   {original_count}")
print(f"After Filtering:   {after_filter_count}")
print(f"Final Unique Routes: {len(df_final)}")
print(f"Total Reduced:     {original_count - len(df_final)} rows")
print(f"Saved to: {OUTPUT_FILE}")
print("="*40)