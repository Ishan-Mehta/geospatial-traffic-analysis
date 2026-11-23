"""Google's path and the roads Gemini named, for two benchmark queries.

Gemini answers with road names, not coordinates, so its roads are drawn as the OpenStreetMap roads near the trip
whose names match the names it gave (same token-set similarity rule as the benchmark, score >= 85).

Usage: python paths_figure.py <project_root> <output dir>
"""
import sys, json, re, difflib
import xml.etree.ElementTree as ET
import numpy as np, pandas as pd
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt

R, OUT = sys.argv[1], sys.argv[2]
QUERIES = [("R065", "Tuesday", "AM_PEAK", "(a) Tin Factory Jn. to Hennur Cross"),
           ("R055", "Tuesday", "AM_PEAK", "(b) Trinity Circle to MG Road Metro")]
plt.rcParams.update({"font.family": "serif", "font.serif": ["Times New Roman", "Nimbus Roman", "DejaVu Serif"],
                     "font.size": 8, "legend.frameon": False})

STOP = {"bengaluru", "bangalore", "karnataka", "india", "the"}
GENERIC = {"road", "rd", "main", "service", "cross", "street", "st", "lane", "flyover", "underpass", "ramp",
           "approach", "access", "loop", "towards", "near", "junction", "interchange", "connector", "nh", "orr"}
ABBR = {"rd": "road", "orr": "outer ring road", "mg": "mahatma gandhi", "st": "street"}


def tokens(s):
    s = re.sub(r"[^a-z0-9 ]+", " ", str(s).lower())
    out = []
    for t in s.split():
        out += ABBR.get(t, t).split()
    return [t for t in out if t not in STOP]


def tsr(a, b):  # token-set similarity, 0-100 (same rule as the benchmark)
    ta, tb = set(tokens(a)), set(tokens(b))
    if not ta or not tb:
        return 0.0
    inter = " ".join(sorted(ta & tb))
    sa = (inter + " " + " ".join(sorted(ta - tb))).strip(); sb = (inter + " " + " ".join(sorted(tb - ta))).strip()
    r = lambda x, y: difflib.SequenceMatcher(None, x, y).ratio() if x and y else 0.0
    return 100 * max(r(inter, sa), r(inter, sb), r(sa, sb))


def name_parts(llm_road):
    """'Outer Ring Road (NH 44 / ORR)' -> ['Outer Ring Road']; 'A / B' -> ['A', 'B']."""
    base = re.sub(r"\([^)]*\)", " ", llm_road)
    return [p.strip() for p in base.split("/") if set(tokens(p)) - GENERIC]


# Queries, Gemini roads and landmark coordinates
d = pd.read_csv(f"{R}/data/benchmark_round2/results/gemini_38_flash/comparison_gemini_38_flash_A.csv")
d = d[d.sample_idx == 0]
od = pd.read_csv(f"{R}/data/benchmark_v2/od_pairs.csv").set_index("route_id")
want = {(q[0], q[1], q[2]) for q in QUERIES}
paths = {}
with open(f"{R}/data/benchmark_round2/gmaps/gmaps_responses.jsonl") as f:
    for line in f:
        if not any(q[0] in line[:60] for q in QUERIES):
            continue
        r = json.loads(line)
        k = (r.get("route_id"), r.get("day"), r.get("slot_id"))
        if k in want and r.get("routes"):
            paths[k] = np.array(r["routes"][0]["polyline"])

# Bounding box of both trips, then OSM edges inside it (streamed from the GraphML file)
boxes = {}
for q in QUERIES:
    p = paths[q[:3]]; o = od.loc[q[0]]
    xs = np.r_[p[:, 0], o.origin_lng, o.dest_lng]; ys = np.r_[p[:, 1], o.origin_lat, o.dest_lat]
    padx = max(0.004, 0.18 * (xs.max() - xs.min())); pady = max(0.004, 0.18 * (ys.max() - ys.min()))
    boxes[q[0]] = (xs.min() - padx, xs.max() + padx, ys.min() - pady, ys.max() + pady)
X0 = min(b[0] for b in boxes.values()); X1 = max(b[1] for b in boxes.values())
Y0 = min(b[2] for b in boxes.values()); Y1 = max(b[3] for b in boxes.values())

NS = "{http://graphml.graphdrawing.org/xmlns}"
keys, nodes, edges = {}, {}, []
for ev, el in ET.iterparse(f"{R}/output/bangalore_drive.graphml", events=("end",)):
    tag = el.tag.replace(NS, "")
    if tag == "key":
        keys[el.get("id")] = el.get("attr.name")
    elif tag == "node":
        a = {keys[c.get("key")]: c.text for c in el}
        nodes[el.get("id")] = (float(a["x"]), float(a["y"]))
        el.clear()
    elif tag == "edge":
        u, v = nodes.get(el.get("source")), nodes.get(el.get("target"))
        if u and v and (X0 <= u[0] <= X1 and Y0 <= u[1] <= Y1 or X0 <= v[0] <= X1 and Y0 <= v[1] <= Y1):
            a = {keys[c.get("key")]: c.text for c in el}
            if a.get("geometry"):
                pts = re.findall(r"(-?\d+\.\d+) (-?\d+\.\d+)", a["geometry"])
                line = np.array([[float(x), float(y)] for x, y in pts])
            else:
                line = np.array([u, v])
            nm = a.get("name") or ""
            nm = re.sub(r"[\[\]']", "", nm)
            edges.append((line, [n.strip() for n in nm.split(",") if n.strip()], a.get("highway", "")))
        el.clear()

MAJOR = ("motorway", "trunk", "primary", "secondary", "tertiary")
fig, axs = plt.subplots(1, 2, figsize=(3.5, 1.85))
for ax, (rid, day, slot, title) in zip(axs, QUERIES):
    x0, x1, y0, y1 = boxes[rid]
    row = d[(d.route_id == rid) & (d.day == day) & (d.slot_id == slot)].iloc[0]
    parts = [p for road in str(row.llm_roads).split(" | ") for p in name_parts(road)]
    for line, names, hw in edges:
        if not ((x0 <= line[:, 0]).any() and (line[:, 0] <= x1).any() and (y0 <= line[:, 1]).any() and (line[:, 1] <= y1).any()):
            continue
        major = any(m in hw for m in MAJOR)
        ax.plot(line[:, 0], line[:, 1], color="#d9d9d9" if major else "#ececec", lw=0.6 if major else 0.3, zorder=1)
        if names and parts and any(set(tokens(n)) - GENERIC and tsr(p, n) >= 85 for p in parts for n in names):
            ax.plot(line[:, 0], line[:, 1], color="#eb6834", lw=2.4, alpha=0.75, solid_capstyle="round", zorder=2)
    p = paths[(rid, day, slot)]
    ax.plot(p[:, 0], p[:, 1], color="#2a78d6", lw=1.1, zorder=3)
    o = od.loc[rid]
    ax.plot(o.origin_lng, o.origin_lat, "o", ms=4, color="#222", zorder=4)
    ax.plot(o.dest_lng, o.dest_lat, "s", ms=4, color="#222", zorder=4)
    ax.set_xlim(x0, x1); ax.set_ylim(y0, y1); ax.set_aspect(1 / np.cos(np.radians(12.97)))
    ax.set_xticks([]); ax.set_yticks([])
    for s in ax.spines.values(): s.set_color("#bbbbbb"); s.set_linewidth(0.5)
    ax.set_title(title, fontsize=6.8)
    print(rid, "Google %.1f km %.0f min | Gemini %.1f km %.0f min | parts %s" % (row.g_km, row.g_min, row.llm_km, row.llm_min, parts))
axs[0].plot([], [], color="#2a78d6", lw=1.1, label="Google's path")
axs[0].plot([], [], color="#eb6834", lw=2.4, alpha=0.75, label="Roads Gemini named")
axs[0].plot([], [], "o", ms=3.5, color="#222", label="Start"); axs[0].plot([], [], "s", ms=3.5, color="#222", label="End")
fig.legend(loc="lower center", ncol=4, fontsize=6.5, handlelength=1.4, columnspacing=1.0, bbox_to_anchor=(0.5, -0.01))
fig.tight_layout(pad=0.3, w_pad=0.5, rect=(0, 0.06, 1, 1))
fig.savefig(f"{OUT}/fig_paths.pdf"); plt.close(fig)
print("edges in box", len(edges))
