# Map of the 72 benchmark routes (OpenStreetMap shortest paths used for route selection) and their landmarks.
# Usage: python routes_map.py <project_root> <out_pdf>
import json, sys
import numpy as np
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
R, OUT = sys.argv[1], sys.argv[2]
plt.rcParams.update({"font.family": "serif", "font.serif": ["Times New Roman", "Nimbus Roman", "DejaVu Serif"], "font.size": 8,
                     "legend.frameon": False})
legs = json.load(open(f"{R}/data/benchmark_v2/hotspot_legs.geojson"))
od = json.load(open(f"{R}/data/benchmark_v2/od_pairs.geojson"))
fig, ax = plt.subplots(figsize=(3.5, 3.0))
for ft in legs["features"]:
    xs, ys = zip(*ft["geometry"]["coordinates"]); ax.plot(xs, ys, color="#dddddd", lw=0.4, zorder=0)
cols = {"B1_1-5km": "#eb6834", "B2_5-12km": "#2a78d6", "B3_12-25km": "#1baf7a"}
labs = {"B1_1-5km": "1-5 km", "B2_5-12km": "5-12 km", "B3_12-25km": "12-25 km"}
pts = set()
for ft in od["features"]:
    p = ft["properties"]; xs, ys = zip(*ft["geometry"]["coordinates"])
    ax.plot(xs, ys, color=cols[p["band"]], lw=1.0, alpha=0.85, zorder=1)
    pts.add((p["origin_lng"], p["origin_lat"])); pts.add((p["dest_lng"], p["dest_lat"]))
x, y = zip(*pts); ax.scatter(x, y, s=8, color="white", edgecolor="black", linewidth=0.6, zorder=2)
for k in cols: ax.plot([], [], color=cols[k], lw=1.4, label=labs[k])
ax.scatter([], [], s=8, color="white", edgecolor="black", linewidth=0.6, label="Landmark")
ax.legend(loc="lower left", fontsize=7)
ax.set_aspect(1 / np.cos(np.radians(12.97))); ax.set_xticks([]); ax.set_yticks([])
for s in ax.spines.values(): s.set_visible(False)
fig.tight_layout(pad=0.1); fig.savefig(OUT); print(len(od["features"]), "routes,", len(pts), "landmarks")
