import os
import osmnx as ox

# 1. Configure OSMnx to look at your existing cache folder
# (This tells it: "Don't download if you see the file in this folder")
ox.settings.use_cache = True
ox.settings.cache_folder = "./cache"  # Ensure this points to where your JSON files are

GRAPH_FILENAME = "bangalore_drive_network.graphml"

# 2. The Logic: Load GraphML (Fastest) -> Build from Cache (Medium) -> Download (Slowest)
if os.path.exists(GRAPH_FILENAME):
    print(f"✅ Found optimized GraphML! Loading instantly...")
    G = ox.load_graphml(GRAPH_FILENAME)
else:
    print(f"⚠️ GraphML not found. Checking cache/downloading...")
    
    # This line will now automatically use your 44MB JSON file if it matches!
    # It will process that JSON into a graph (this might take 10-20 seconds)
    G = ox.graph_from_place("Bangalore, India", network_type="drive")
    
    # SAVE IT so next time it's instant!
    print(f"💾 Saving optimized GraphML to '{GRAPH_FILENAME}'...")
    ox.save_graphml(G, GRAPH_FILENAME)

print("🚀 Graph ready! Starting routing...")