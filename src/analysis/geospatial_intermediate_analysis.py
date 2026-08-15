import os
import pandas as pd
import numpy as np
import osmnx as ox
import networkx as nx
import matplotlib.pyplot as plt
import seaborn as sns

# ==========================================
# CONFIGURATION - CHANGE THESE PATHS
# ==========================================
# Input files (Outputs from Script 1)
FLATTENED_TRAFFIC_CSV = '../../output/flattened_traffic_data.csv'
MASTER_SUBROUTES_CSV = '../../output/master_subroutes.csv'

# Create the results directory if it doesn't exist
os.makedirs('../../output/results', exist_ok=True)

# Output files for Script 2
BOTTLENECK_ANALYSIS_CSV = '../../output/results/bottleneck_analysis.csv'
TOP_20_CONGESTED_PLOT = '../../output/results/top_20_congested.png'
TOP_5_UNPREDICTABLE_PLOT = '../../output/results/top_5_unpredictable.png'

# New paths for the distributions and rankings
DISTANCE_RANK_CSV = '../../output/results/all_subroutes_by_distance.csv'
DELAY_RANK_CSV = '../../output/results/all_subroutes_by_delay.csv'
SPEED_RANK_CSV = '../../output/results/all_subroutes_by_speed.csv'
DEL_VAR_RANK_CSV = '../../output/results/all_subroutes_by_variance_delay.csv'
CONGTN_RATIO_CSV = '../../output/results/all_subroutes_by_congestion_ratio.csv'
DURATION_CSV = '../../output/results/all_subroutes_by_duration.csv'
RATIO_VOL_RANK_CSV = '../../output/results/all_subroutes_by_ratio_volatility.csv'

DIST_DISTANCE_PLOT = '../../output/results/distribution_distance.png'
DIST_DELAY_PLOT = '../../output/results/distribution_avg_delay.png'
DIST_SPEED_PLOT = '../../output/results/distribution_avg_speed.png'
SCATTER_PLOT = '../../output/results/network_health_scatter.png'
DIST_STD_DEV_PLOT = '../../output/results/distribution_std_dev_delay.png'
DIST_DURATION_PLOT = '../../output/results/distribution_avg_duration.png'
DIST_CONGESTN_RATIO_PLOT = '../../output/results/distribution_avg_congestion_ratio.png'
DIST_STD_DEV_RATIO_VOL_PLOT = '../../output/results/distribution_volatilty.png'
TOP_20_CONGTN_RATIO_PLOT = '../../output/results/top_20_congestion_ratio.png'
# TOP_5_UNPREDICTABLE_CONGESTION_PLOT = '../../output/results/top_5_unpredictable_congestion_volatility.png'
SCATTER_CONGESTION_VOLATILITY_PLOT = '../../output/results/scatter_congestion_vs_volatility.png'



# OSM Graph File - We save it locally to speed up subsequent runs
OSM_GRAPH_PATH = '../../output/bangalore_drive.graphml'
PLACE_NAME = "Bangalore, Karnataka, India"
# ==========================================

def load_or_download_osm_graph():
    """
    Loads the OSM graph from a local file if it exists.
    Otherwise, downloads it from OpenStreetMap and saves it.
    """
    if os.path.exists(OSM_GRAPH_PATH):
        print(f"Loading local OSM graph from {OSM_GRAPH_PATH}...")
        G = ox.load_graphml(OSM_GRAPH_PATH)
    else:
        print(f"Downloading OSM graph for {PLACE_NAME} (This might take a few minutes)...")
        # network_type='drive' ensures we only get drivable roads, ignoring footpaths
        G = ox.graph_from_place(PLACE_NAME, network_type='drive')
        ox.save_graphml(G, OSM_GRAPH_PATH)
        print("Graph downloaded and saved locally.")
    
    return G

# Load the graph globally so we don't have to pass it around constantly
print("Initializing geospatial network...")
G = load_or_download_osm_graph()

def calculate_fallback_static_duration(start_lat, start_lng, end_lat, end_lng):
    """
    Uses OSMnx to snap GPS coordinates to the nearest road edge, 
    retrieves its length and speed limit, and calculates free-flow duration.
    """
    try:
        # Snap the midpoint of the start/end coordinates to the nearest network edge
        mid_lat = (float(start_lat) + float(end_lat)) / 2.0
        mid_lng = (float(start_lng) + float(end_lng)) / 2.0
        
        # ox.distance.nearest_edges expects (G, X, Y) where X is longitude, Y is latitude
        nearest_edge = ox.distance.nearest_edges(G, X=mid_lng, Y=mid_lat)
        
        # Extract edge attributes
        u, v, key = nearest_edge
        edge_data = G.get_edge_data(u, v)[key]
        
        # Length in meters
        length_m = edge_data.get('length', 0)
        
        # Max speed limit in km/h. OSM sometimes returns a list if multiple limits exist
        maxspeed = edge_data.get('maxspeed', 40) # Default to 40 km/h if missing in OSM
        if isinstance(maxspeed, list):
            maxspeed = int(maxspeed[0])
        elif isinstance(maxspeed, str):
            maxspeed = int(maxspeed.replace(' mph', '').replace(' km/h', ''))
            
        # Convert max speed to meters per second (1 km/h = 1/3.6 m/s)
        speed_mps = maxspeed / 3.6
        
        # Calculate duration in seconds (Time = Distance / Speed)
        if speed_mps > 0 and length_m > 0:
            return int(length_m / speed_mps)
        else:
            return 0
            
    except Exception as e:
        # If snapping fails (e.g., coordinates too far from any known road), return 0
        return 0
    
def process_and_engineer_features():
    """
    Loads the CSVs, patches missing static durations using OSMnx, 
    merges the spatial data with the time-series data, and engineers 
    speed and delay metrics.
    """
    print("Loading datasets into memory...")
    df_traffic = pd.read_csv(FLATTENED_TRAFFIC_CSV)
    df_subroutes = pd.read_csv(MASTER_SUBROUTES_CSV)
    
    # ---------------------------------------------------------
    # 1. The OSMnx Fallback Check (Applied to Master File for Efficiency)
    # ---------------------------------------------------------
    # Identify rows where static_duration is missing, NaN, or 0
    missing_static_mask = (df_subroutes['static_duration_s'].isnull()) | (df_subroutes['static_duration_s'] <= 0)
    
    if missing_static_mask.any():
        num_missing = missing_static_mask.sum()
        print(f"Found {num_missing} sub-routes missing static_duration. Applying OSMnx fallback...")
        
        # Apply our fallback function row by row ONLY to the missing records
        df_subroutes.loc[missing_static_mask, 'static_duration_s'] = df_subroutes[missing_static_mask].apply(
            lambda row: calculate_fallback_static_duration(
                row['start_lat'], row['start_lng'], 
                row['end_lat'], row['end_lng']
            ), axis=1
        )
        
        # Save the repaired master file so we never have to run OSMnx for these again
        df_subroutes.to_csv(MASTER_SUBROUTES_CSV, index=False)
        print("OSMnx fallback complete. Repaired master_subroutes.csv saved.")
    else:
        print("No missing static_durations found. Skipping OSMnx fallback.")

    # ---------------------------------------------------------
    # 2. Merge Datasets
    # ---------------------------------------------------------
    print("Merging traffic snapshots with spatial master data...")
    # FIX: We rename the master static duration to 'fallback_static_s' so it doesn't 
    # overwrite the time-specific 'static_duration_s' currently living in df_traffic.
    df_subroutes_merge = df_subroutes.rename(columns={'static_duration_s': 'fallback_static_s'})
    df_merged = pd.merge(df_traffic, df_subroutes_merge, on='sub_route_id', how='left')
    
    # ---------------------------------------------------------
    # 3. Feature Engineering: Delay & Speed
    # ---------------------------------------------------------
    print("Calculating Speed (km/h) and Delay (seconds)...")
    
    # FIX: Create a 'final_static_s' column. Use the timestamp-specific one from Google, 
    # but if it is missing/0, fall back to the OSMnx one from the master file.
    df_merged['final_static_s'] = np.where(
        (df_merged['static_duration_s'].isnull()) | (df_merged['static_duration_s'] <= 0),
        df_merged['fallback_static_s'],
        df_merged['static_duration_s']
    )
    
    # Delay = Actual Time - Expected Time
    df_merged['delay_s'] = df_merged['live_duration_s'] - df_merged['static_duration_s']
    
    
    # Congestion Ratio (Delay / Expected Time)
    # We use np.where to prevent division by zero if final_static_s is somehow 0
    df_merged['congestion_ratio'] = np.where(
        df_merged['final_static_s'] > 0,
        df_merged['delay_s'] / df_merged['final_static_s'],
        0
    )
    
    
    # Speed = Distance / Time. 
    # Formula: (Meters / 1000) / (Seconds / 3600)
    # We use np.where to prevent division by zero errors if live_duration_s is somehow 0
    df_merged['speed_kmph'] = np.where(
        df_merged['live_duration_s'] > 0,
        (df_merged['distance_meters'] / 1000) / (df_merged['live_duration_s'] / 3600),
        0 
    )
    
    return df_merged



def analyze_and_visualize(df_merged):
    """
    Aggregates the engineered features to identify bottlenecks, 
    exports comprehensive CSVs, and generates multiple analytical plots.
    """
    print("Aggregating bottleneck metrics...")
    
    # 1. Group by sub_route_id and calculate multiple metrics
    bottleneck_stats = df_merged.groupby('sub_route_id').agg({
        'road_name': 'first',
        'distance_meters': 'first',
        'live_duration_s': ['mean'],
        'delay_s': ['mean', 'max', 'std'],
        'congestion_ratio': ['mean', 'max', 'std'],
        'speed_kmph': ['mean', 'min'],
        'timestamp': 'count' 
    }).reset_index()
    
    bottleneck_stats.columns = [
        'sub_route_id', 'road_name', 'distance_meters',
        'avg_live_duration_s',
        'avg_delay_s', 'max_delay_s', 'delay_std_dev', 
        'avg_congestion_ratio', 'max_congestion_ratio', 'ratio_std_dev',
        'avg_speed_kmph', 'min_speed_kmph', 
        'snapshot_count'
    ]
    
    # Filter out statistically insignificant routes
    # Lowered to 1 for testing. Change to 40 for the 7-day dataset!
    bottleneck_stats = bottleneck_stats[bottleneck_stats['snapshot_count'] >= 1]
    bottleneck_stats['delay_std_dev'] = bottleneck_stats['delay_std_dev'].fillna(0)
    bottleneck_stats['ratio_std_dev'] = bottleneck_stats['ratio_std_dev'].fillna(0)
    
    # ---------------------------------------------------------
    # 2. Add Rankings & Export Comprehensive CSVs
    # ---------------------------------------------------------
    print("Generating ranked CSVs...")
    
    bottleneck_stats.to_csv(BOTTLENECK_ANALYSIS_CSV, index=False)
    print(f"Saved: {BOTTLENECK_ANALYSIS_CSV}")
    
    # NEW: Sort by Distance
    distance_sorted = bottleneck_stats.sort_values(by='distance_meters', ascending=False).copy()
    distance_sorted.insert(0, 'distance_rank', range(1, len(distance_sorted) + 1))
    distance_sorted.to_csv(DISTANCE_RANK_CSV, index=False)
    
    # Sort by Delay (Worst bottlenecks first)
    delay_sorted = bottleneck_stats.sort_values(by='avg_delay_s', ascending=False).copy()
    delay_sorted.insert(0, 'delay_rank', range(1, len(delay_sorted) + 1)) # Adds a ranking ID (1 is worst)
    delay_sorted.to_csv(DELAY_RANK_CSV, index=False)
    
    # Sort by Speed (Slowest routes first)
    speed_sorted = bottleneck_stats.sort_values(by='avg_speed_kmph', ascending=True).copy()
    speed_sorted.insert(0, 'speed_rank', range(1, len(speed_sorted) + 1)) # Adds a ranking ID (1 is slowest)
    speed_sorted.to_csv(SPEED_RANK_CSV, index=False)
    
    # NEW: Sort by Variance (Unpredictability)
    variance_sorted = bottleneck_stats.sort_values(by='delay_std_dev', ascending=False).copy()
    variance_sorted.insert(0, 'variance_rank', range(1, len(variance_sorted) + 1))
    variance_sorted.to_csv(DEL_VAR_RANK_CSV, index=False)
    
    # NEW: Sort by Congestion Ratio (Highest relative congestion first)
    ratio_sorted = bottleneck_stats.sort_values(by='avg_congestion_ratio', ascending=False).copy()
    ratio_sorted.insert(0, 'ratio_rank', range(1, len(ratio_sorted) + 1))
    ratio_sorted.to_csv(CONGTN_RATIO_CSV, index=False)
    
    # NEW: Sort by Live Duration (Longest time spent first)
    duration_sorted = bottleneck_stats.sort_values(by='avg_live_duration_s', ascending=False).copy()
    duration_sorted.insert(0, 'duration_rank', range(1, len(duration_sorted) + 1))
    duration_sorted.to_csv(DURATION_CSV, index=False)
    
    # NEW: Sort by Ratio Volatility (Most unpredictable relative to expected)
    ratio_vol_sorted = bottleneck_stats.sort_values(by='ratio_std_dev', ascending=False).copy()
    ratio_vol_sorted.insert(0, 'ratio_vol_rank', range(1, len(ratio_vol_sorted) + 1))
    ratio_vol_sorted.to_csv(RATIO_VOL_RANK_CSV, index=False)
     # Add this with your other print statements
    
    print(f"Saved: {DISTANCE_RANK_CSV}")
    print(f"Saved: {DELAY_RANK_CSV}")
    print(f"Saved: {SPEED_RANK_CSV}")
    print(f"Saved: {DEL_VAR_RANK_CSV}")
    print(f"Saved: {CONGTN_RATIO_CSV}")
    print(f"Saved: {DURATION_CSV}")
    print(f"Saved: {RATIO_VOL_RANK_CSV}")

    # ---------------------------------------------------------
    # 3. Visualizations
    # ---------------------------------------------------------
    print("Generating statistical plots...")
    sns.set_theme(style="whitegrid")
    
    # --- 1. Distribution of Average Delays ---
    plt.figure(figsize=(10, 6))
    # A histogram shows the count of sub-routes falling into different delay buckets
    sns.histplot(data=bottleneck_stats, x='avg_delay_s', bins=30, kde=True, color='crimson')
    plt.title('Distribution of Average Delays Across All Sub-routes', fontsize=16)
    plt.xlabel('Average Delay (Seconds)', fontsize=12)
    plt.ylabel('Number of Sub-routes', fontsize=12)
    plt.tight_layout()
    plt.savefig(DIST_DELAY_PLOT, dpi=300)
    plt.close()
    print(f"Saved: {DIST_DELAY_PLOT}")

    # --- 2. Distribution of Average Speeds ---
    plt.figure(figsize=(10, 6))
    sns.histplot(data=bottleneck_stats, x='avg_speed_kmph', bins=30, kde=True, color='teal')
    plt.title('Distribution of Average Speeds Across All Sub-routes', fontsize=16)
    plt.xlabel('Average Speed (km/h)', fontsize=12)
    plt.ylabel('Number of Sub-routes', fontsize=12)
    plt.tight_layout()
    plt.savefig(DIST_SPEED_PLOT, dpi=300)
    plt.close()
    print(f"Saved: {DIST_SPEED_PLOT}")
    
    
    # --- 3. Distribution of Standard Deviation in Delay ---
    plt.figure(figsize=(10, 6))
    sns.histplot(data=bottleneck_stats[bottleneck_stats['delay_std_dev'] <= 400], x='delay_std_dev', bins=30, kde=True, color='indigo')
    plt.title('Distribution of Sub-route Delay Std Dev', fontsize=16)
    plt.xlabel('Std Dev (Seconds)', fontsize=12)
    plt.ylabel('Number of Sub-routes', fontsize=12)
    plt.tight_layout()
    plt.savefig(DIST_STD_DEV_PLOT, dpi=300)
    plt.close()
    
    # --- 4. Distribution of Distances ---
    plt.figure(figsize=(10, 6))
    sns.histplot(data=bottleneck_stats[bottleneck_stats['distance_meters'] <= 7500], x='distance_meters', bins=30, kde=True, color='indigo')
    plt.title('Distribution of Sub-route Distances', fontsize=16)
    plt.xlabel('Distance (Meters)', fontsize=12)
    plt.ylabel('Number of Sub-routes', fontsize=12)
    plt.tight_layout()
    plt.savefig(DIST_DISTANCE_PLOT, dpi=300)
    plt.close()
    

    # --- 5. Top 20 Most Congested Routes (By Average Delay) ---
    top_20_congested = delay_sorted.head(20).copy()
    
    plt.figure(figsize=(12, 8))
    short_names = top_20_congested['road_name'].str.slice(0, 35)
    top_20_congested['display_name'] = short_names + "\n(" + top_20_congested['sub_route_id'].str[4:9] + ")"
    
    sns.barplot(
        x='avg_delay_s', 
        y='display_name', 
        data=top_20_congested, 
        hue='display_name',
        legend=False,
        palette='Reds_r'
    )
    plt.title('Top 20 Most Congested Sub-routes (Average Delay)', fontsize=16)
    plt.xlabel('Average Delay (Seconds)', fontsize=12)
    plt.ylabel('Road Segment', fontsize=12)
    plt.tight_layout()
    plt.savefig(TOP_20_CONGESTED_PLOT, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"Saved: {TOP_20_CONGESTED_PLOT}")

    # --- 6. Top 5 Most Unpredictable Routes (By Delay Std Deviation) ---
    top_5_unpredictable = bottleneck_stats.sort_values(by='delay_std_dev', ascending=False).head(5)
    unpredictable_ids = top_5_unpredictable['sub_route_id'].tolist()
    
    df_unpredictable_raw = df_merged[df_merged['sub_route_id'].isin(unpredictable_ids)].copy()
    id_to_name = dict(zip(top_5_unpredictable['sub_route_id'], top_5_unpredictable['road_name']))
    
    mapped_names = df_unpredictable_raw['sub_route_id'].map(id_to_name).fillna('Unknown Road').astype(str).str.slice(0, 20)
    short_ids = df_unpredictable_raw['sub_route_id'].astype(str).str[4:9]
    df_unpredictable_raw['road_label'] = mapped_names + "\n(" + short_ids + ")"
    
    plt.figure(figsize=(10, 6))
    sns.boxplot(
        x='road_label', 
        y='delay_s', 
        data=df_unpredictable_raw, 
        hue='road_label',
        legend=False,
        palette='Set2'
    )
    plt.title('Delay Volatility for Top 5 Unpredictable Routes', fontsize=16)
    plt.xlabel('Road Segment', fontsize=12)
    plt.ylabel('Delay Distribution (Seconds)', fontsize=12)
    # plt.tight_layout()
    plt.xticks(rotation=45, ha='right')
    plt.savefig(TOP_5_UNPREDICTABLE_PLOT, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"Saved: {TOP_5_UNPREDICTABLE_PLOT}")
    
    # --- 6. Network Health Scatter Plot ---
    plt.figure(figsize=(10, 6))
    sns.scatterplot(
        x='avg_delay_s', 
        y='avg_speed_kmph', 
        data=bottleneck_stats, 
        alpha=0.5, 
        color='purple'
    )
    plt.title('Network Health: Avg Speed vs Avg Delay', fontsize=16)
    plt.xlabel('Average Delay (Seconds)', fontsize=12)
    plt.ylabel('Average Speed (km/h)', fontsize=12)
    plt.tight_layout()
    plt.savefig(SCATTER_PLOT, dpi=300)
    plt.close()
    print(f"Saved: {SCATTER_PLOT}")
    
    # --- 7. Distribution of Average Live Durations ---
    plt.figure(figsize=(10, 6))
    # Filtering out extreme outliers (> 30 mins) to keep the distribution readable
    sns.histplot(data=bottleneck_stats[bottleneck_stats['avg_live_duration_s'] <= 1800], x='avg_live_duration_s', bins=30, kde=True, color='forestgreen')
    plt.title('Distribution of Average Leg Durations (Under 30 mins)', fontsize=16)
    plt.xlabel('Average Live Duration (Seconds)', fontsize=12)
    plt.ylabel('Number of Sub-routes', fontsize=12)
    plt.tight_layout()
    plt.savefig(DIST_DURATION_PLOT, dpi=300)
    plt.close()
    print(f"Saved: {DIST_DURATION_PLOT}")

    # --- 8. Distribution of Congestion Ratios ---
    plt.figure(figsize=(10, 6))
    sns.histplot(data=bottleneck_stats, x='avg_congestion_ratio', bins=30, kde=True, color='darkorange')
    plt.title('Distribution of Average Congestion Ratios', fontsize=16)
    plt.xlabel('Congestion Ratio (Delay / Static Duration)', fontsize=12)
    plt.ylabel('Number of Sub-routes', fontsize=12)
    plt.tight_layout()
    plt.savefig(DIST_CONGESTN_RATIO_PLOT, dpi=300)
    plt.close()
    print(f"Saved: {DIST_CONGESTN_RATIO_PLOT}")

    # ---9. Top 20 Most Structurally Congested Routes (By Ratio) ---
    top_20_ratio = ratio_sorted.head(20).copy()
    
    plt.figure(figsize=(12, 8))
    short_names_ratio = top_20_ratio['road_name'].str.slice(0, 35)
    top_20_ratio['display_name'] = short_names_ratio + "\n(" + top_20_ratio['sub_route_id'].str[4:9] + ")"
    
    sns.barplot(
        x='avg_congestion_ratio', 
        y='display_name', 
        data=top_20_ratio, 
        hue='display_name',
        legend=False,
        palette='Oranges_r'
    )
    plt.title('Top 20 Most Congested Sub-routes by Ratio (Delay/Expected)', fontsize=16)
    plt.xlabel('Average Congestion Ratio', fontsize=12)
    plt.ylabel('Road Segment', fontsize=12)
    plt.savefig(f'{TOP_20_CONGTN_RATIO_PLOT}', dpi=300, bbox_inches='tight')
    plt.close()
    print(f"Saved: {TOP_20_CONGTN_RATIO_PLOT}")
    
    
    # --- ANSWERING THE PROFESSOR'S QUESTION ---
    print("\n--- PROFESSOR'S HYPOTHESIS CHECK ---")
    # Find the threshold for the 75th percentile of Congestion Ratios
    q75_threshold = bottleneck_stats['avg_congestion_ratio'].quantile(0.75)
    
    # Split the data into top 25% and bottom 75%
    top_25_congested = bottleneck_stats[bottleneck_stats['avg_congestion_ratio'] >= q75_threshold]
    bottom_75_congested = bottleneck_stats[bottleneck_stats['avg_congestion_ratio'] < q75_threshold]
    
    # Compare their average variations
    top_25_variance = top_25_congested['ratio_std_dev'].mean()
    bottom_75_variance = bottom_75_congested['ratio_std_dev'].mean()
    
    print(f"75th Percentile Ratio Threshold: {q75_threshold:.3f}")
    print(f"Avg Volatility (Ratio Std Dev) of TOP 25% Congested Roads: {top_25_variance:.3f}")
    print(f"Avg Volatility (Ratio Std Dev) of BOTTOM 75% Roads: {bottom_75_variance:.3f}")
    print("------------------------------------\n")

    # 10. Congestion vs. Volatility Scatter Plot
    # This visually proves the relationship to the professor
    plt.figure(figsize=(10, 6))
    sns.scatterplot(
        x='avg_congestion_ratio', 
        y='ratio_std_dev', 
        data=bottleneck_stats, 
        alpha=0.6, 
        color='blue'
    )
    # Draw a vertical line showing where the 75th percentile starts
    plt.axvline(x=q75_threshold, color='red', linestyle='--', label=f'75th Percentile ({q75_threshold:.4f})')
    
    plt.title('Congestion Ratio vs. Volatility (Unpredictability)', fontsize=16)
    plt.xlabel('Average Congestion Ratio', fontsize=12)
    plt.ylabel('Volatility (Ratio Standard Deviation)', fontsize=12)
    plt.legend()
    plt.tight_layout()
    plt.savefig(SCATTER_CONGESTION_VOLATILITY_PLOT, dpi=300)
    plt.close()
    print(f"Saved: {SCATTER_CONGESTION_VOLATILITY_PLOT}")
    
    
    # 11. Distribution of Volatility (Ratio Standard Deviation) ---
    plt.figure(figsize=(10, 6))
    # Filtering outliers (keeping volatility <= 0.5) to keep the distribution readable
    sns.histplot(
        data=bottleneck_stats[bottleneck_stats['ratio_std_dev'] <= 0.5], 
        x='ratio_std_dev', 
        bins=30, 
        kde=True, 
        color='magenta'
    )
    plt.title('Distribution of Unpredictability (Ratio Volatility)', fontsize=16)
    plt.xlabel('Volatility (Ratio Standard Deviation)', fontsize=12)
    plt.ylabel('Number of Sub-routes', fontsize=12)
    plt.tight_layout()
    plt.savefig(DIST_STD_DEV_RATIO_VOL_PLOT, dpi=300)
    plt.close()
    print(f"Saved: {DIST_STD_DEV_RATIO_VOL_PLOT}")
    
    # 12. Top 5 Most Unpredictable Routes (By Volatility Std Deviation) ---
    # top_5_unpredictable = bottleneck_stats[bottleneck_stats['ratio_std_dev'] <= 2].sort_values(by='ratio_std_dev', ascending=False).head(5)
    # unpredictable_ids = top_5_unpredictable['sub_route_id'].tolist()
    
    # df_unpredictable_raw = df_merged[df_merged['sub_route_id'].isin(unpredictable_ids)].copy()
    # id_to_name = dict(zip(top_5_unpredictable['sub_route_id'], top_5_unpredictable['road_name']))
    
    # mapped_names = df_unpredictable_raw['sub_route_id'].map(id_to_name).fillna('Unknown Road').astype(str).str.slice(0, 20)
    # short_ids = df_unpredictable_raw['sub_route_id'].astype(str).str[4:9]
    # df_unpredictable_raw['road_label'] = mapped_names + "\n(" + short_ids + ")"
    
    # plt.figure(figsize=(10, 6))
    # sns.boxplot(
    #     x='road_label', 
    #     y='congestion_ratio', 
    #     data=df_unpredictable_raw, 
    #     hue='road_label',
    #     legend=False,
    #     palette='Set2'
    # )
    # plt.title('Congestion Ratio Volatility for Top 5 Unpredictable Routes', fontsize=16)
    # plt.xlabel('Road Segment', fontsize=12)
    # plt.ylabel('Congestion Ratio', fontsize=12)
    # # plt.tight_layout()
    # plt.xticks(rotation=45, ha='right')
    # plt.savefig(TOP_5_UNPREDICTABLE_CONGESTION_PLOT, dpi=300, bbox_inches='tight')
    # plt.close()
    # print(f"Saved: {TOP_5_UNPREDICTABLE_CONGESTION_PLOT}")
    
    # 11. Distribution of Volatility (Ratio Standard Deviation) ---
    # plt.figure(figsize=(10, 6))
    # # Filtering outliers (keeping volatility <= 0.02) to keep the distribution readable
    # sns.histplot(
    #     data=bottleneck_stats[bottleneck_stats['ratio_std_dev'] <= 0.02], 
    #     x='ratio_std_dev', 
    #     bins=30, 
    #     kde=True, 
    #     color='magenta'
    # )
    # plt.title('Distribution of Unpredictability (Ratio Volatility) under 0.02', fontsize=16)
    # plt.xlabel('Volatility (Ratio Standard Deviation)', fontsize=12)
    # plt.ylabel('Number of Sub-routes', fontsize=12)
    # plt.tight_layout()
    # plt.savefig('../../output/results/distribution_volatility_very_less.png', dpi=300)
    # plt.close()
    # print("Saved: '../../output/results/distribution_volatility_very_less.png'")

    print("\n" + "="*40)
    print("ANALYSIS COMPLETE")
    print("="*40)
    print(f"Analyzed {len(bottleneck_stats)} distinct sub-routes.")
    worst_road = top_20_congested.iloc[0]['road_name']
    worst_delay = top_20_congested.iloc[0]['avg_delay_s']
    print(f"Worst Bottleneck: {worst_road} (Avg Delay: {worst_delay:.1f}s)")
    print("="*40)

# ==========================================
# MAIN EXECUTION BLOCK
# ==========================================
if __name__ == "__main__":
    # Ensure pandas doesn't give chained assignment warnings during complex indexing
    pd.options.mode.chained_assignment = None 
    
    # Run the pipeline
    merged_data = process_and_engineer_features()
    analyze_and_visualize(merged_data)