import pandas as pd
import osmnx as ox
import networkx as nx
from shapely.geometry import LineString, Point
import os

########################################################################

INPUT_FILE = '../../data/processed/geocoded_optimised_blr_roads.csv'
OUTPUT_FILE = '../../output/qgis_optimised_blr_routes.geojson'

# INPUT_FILE = './data/geocoded_blr_arterial_roads_chain.csv'
# OUTPUT_FILE = './data/qgis_arterial_blr_routes.geojson'

# INPUT_FILE = './data/geocoded_blr_sub_arterial_roads_chain.csv'
# OUTPUT_FILE = './data/qgis_sub_arterial_blr_routes.geojson'

########################################################################

# --- 1. SETUP & LOAD MAP (Clean & Undirected) ---
GRAPH_FILENAME = "bangalore_drive.graphml"

# Force cache settings
ox.settings.use_cache = True
ox.settings.cache_folder = "./cache"

print("⏳ Loading Map...")
if os.path.exists(GRAPH_FILENAME):
    G = ox.load_graphml(GRAPH_FILENAME)
else:
    print("   Building map from scratch (using your downloaded cache)...")
    G = ox.graph_from_place("Bangalore, India", network_type="drive")
    # Save purely for future speed
    ox.save_graphml(G, GRAPH_FILENAME)

# CRITICAL STEP: Convert to Undirected to stop "No Path" errors on one-way streets
print("🚦 Converting to Undirected Graph (allows 2-way travel)...")
G = G.to_undirected()
print("✅ Map Ready.")

# --- 2. THE DEBUGGED ROUTING FUNCTION ---
def get_route_debug(row):
    # Extract the chain and the ID for error reporting
    coord_chain = row['Full_Coordinate_Chain']
    road_id = row.get('Sl_No', 'Unknown ID')

    try:
        # Check for empty data
        if pd.isna(coord_chain) or str(coord_chain).strip() == "":
            return None
        
        # CLEANING: Split by pipe, then strip whitespace
        raw_points = [p.strip() for p in str(coord_chain).split('|') if p.strip()]
        
        points = []
        for p in raw_points:
            try:
                # Split by comma
                parts = p.split(',')
                if len(parts) != 2:
                    print(f"   ⚠️ Row {road_id}: Skipping malformed point '{p}'")
                    continue
                
                lat = float(parts[0].strip())
                lon = float(parts[1].strip())
                points.append((lat, lon))
            except ValueError as ve:
                print(f"   ⚠️ Row {road_id}: Value Error on point '{p}' -> {ve}")
                continue

        if len(points) < 2:
            print(f"   ℹ️ Row {road_id}: Ignored (Less than 2 valid points)")
            return None

        full_route_nodes = []
        
        for i in range(len(points) - 1):
            u_lat, u_lon = points[i]
            v_lat, v_lon = points[i+1]
            
            # Snap to nearest nodes (X=Lon, Y=Lat)
            orig_node = ox.distance.nearest_nodes(G, u_lon, u_lat)
            dest_node = ox.distance.nearest_nodes(G, v_lon, v_lat)
            
            # Skip if start and end snapped to the same node (distance = 0)
            if orig_node == dest_node:
                continue

            # Calculate Path
            segment = nx.shortest_path(G, orig_node, dest_node, weight='length')
            
            if i > 0:
                full_route_nodes.extend(segment[1:])
            else:
                full_route_nodes.extend(segment)

        if len(full_route_nodes) < 2:
            return None

        # Build Geometry
        node_geoms = [Point(G.nodes[n]['x'], G.nodes[n]['y']) for n in full_route_nodes]
        return LineString(node_geoms)

    except nx.NetworkXNoPath:
        print(f"   ❌ Row {road_id}: No path possible between points (Disconnected road?)")
        return None
    except Exception as e:
        # THIS WILL PRINT THE REAL ERROR
        print(f"   🔥 CRITICAL ERROR Row {road_id}: {str(e)}")
        return None


df = pd.read_csv(INPUT_FILE)

print(f"🚀 Processing {len(df)} routes calculation...")

# Apply the function to the whole row (axis=1) so we can print the ID in errors
df['geometry'] = df.apply(get_route_debug, axis=1)

# Success Check
successes = df['geometry'].notna().sum()
print(f"🏁 Finished. Generated {successes} valid routes.")

if successes > 0:
    print('Generating GeoJSON file!...')
    import geopandas as gpd
    gdf = gpd.GeoDataFrame(df.dropna(subset=['geometry']), geometry='geometry', crs="EPSG:4326")
    gdf.to_file(OUTPUT_FILE, driver='GeoJSON')
    print(f"💾 Saved to '{OUTPUT_FILE}'")

else:
    print('No valid routes. No output file generated!')




# import pandas as pd
# import osmnx as ox
# import networkx as nx
# from shapely.geometry import LineString, Point
# import os

# # --- PART 1: LOAD OR CREATE THE MAP ---
# GRAPH_FILENAME = "bangalore_drive_network.graphml"

# # Configure cache so we can use your JSON files if needed
# ox.settings.use_cache = True
# ox.settings.cache_folder = "./cache"

# if os.path.exists(GRAPH_FILENAME):
#     print(f"✅ Found local map file! Loading '{GRAPH_FILENAME}'...")
#     G = ox.load_graphml(GRAPH_FILENAME)
# else:
#     print(f"⚠️ Map file not found. Building from cache/download...")
#     G = ox.graph_from_place("Bangalore, India", network_type="drive")
    
#     # CRITICAL FIX for "No Path" Errors:
#     # Keep only the largest "Strongly Connected Component".
#     # This removes isolated islands where you can get stuck.
#     print("🔧 Sanitizing graph (removing isolated road islands)...")
#     G = ox.truncate.largest_component(G, strongly=True)
    
#     print(f"💾 Saving sanitized map to '{GRAPH_FILENAME}'...")
#     ox.save_graphml(G, GRAPH_FILENAME)

# # ... (after loading G)

# print("🚦 converting to 'Undirected' to ignore one-way rules...")
# G = G.to_undirected()

# # ... (rest of the script)

# print("🚀 Map is ready. Starting the routing engine...")

# # --- PART 2: THE ROUTING FUNCTION ---
# def get_route(coord_chain):
#     try:
#         if pd.isna(coord_chain): return None
        
#         # 1. Parse Data
#         raw_points = coord_chain.split('|')
#         points = []
#         for p in raw_points:
#             lat, lon = map(float, p.split(','))
#             points.append((lat, lon))
        
#         if len(points) < 2: return None

#         full_route_nodes = []
        
#         # 2. Calculate Segments
#         for i in range(len(points) - 1):
#             u_lat, u_lon = points[i]
#             v_lat, v_lon = points[i+1]
            
#             # Snap to nearest nodes
#             orig_node = ox.distance.nearest_nodes(G, u_lon, u_lat)
#             dest_node = ox.distance.nearest_nodes(G, v_lon, v_lat)
            
#             # CHECK: If start/end are the same node, skip routing
#             if orig_node == dest_node:
#                 continue 
            
#             # Routing (Now safe because G is Undirected!)
#             segment = nx.shortest_path(G, orig_node, dest_node, weight='length')
            
#             # Add segment to list
#             if i > 0: full_route_nodes.extend(segment[1:])
#             else: full_route_nodes.extend(segment)

#         # 3. SAFETY CHECK: Do we have enough nodes for a line?
#         if len(full_route_nodes) < 2:
#             return None # The route was too short to draw
            
#         # Convert to Geometry
#         node_geoms = [Point(G.nodes[n]['x'], G.nodes[n]['y']) for n in full_route_nodes]
#         return LineString(node_geoms)

#     except Exception as e:
#         # This prints the SPECIFIC error so you know if it's "NoPath" or "LineString"
#         print(f"⚠️ Error on row: {e}") 
#         return None

# # --- PART 3: LOAD CSV AND RUN ---
# # Replace with your actual CSV loading
# # df = pd.read_csv('your_file.csv')

# # (Demo Data for testing)
# # data = """Zone,Sl_No,Full_Coordinate_Chain,Status
# # Mahadevapura -2,S-02,"13.0249798,77.6944104|13.0249798,77.6944104|13.0373995,77.69272099999999",OK
# # """
# from io import StringIO
# df = pd.read_csv('bangalore_roads_geocoded_chain.csv') 

# print("Calculating routes...")
# # Only process rows where Status is OK
# mask = df['Status'] == 'OK'
# df.loc[mask, 'geometry'] = df.loc[mask, 'Full_Coordinate_Chain'].apply(get_route)

# # Filter out failed routes (where geometry is None)
# df_final = df.dropna(subset=['geometry'])

# # --- PART 4: SAVE TO GEOJSON ---
# import geopandas as gpd
# if not df_final.empty:
#     gdf = gpd.GeoDataFrame(df_final, geometry='geometry', crs="EPSG:4326")
#     gdf.to_file("bangalore_real_routes.geojson", driver='GeoJSON')
#     print(f"🎉 Success! Saved {len(df_final)} routes to 'bangalore_real_routes.geojson'")
# else:
#     print("😔 No valid routes could be calculated.")