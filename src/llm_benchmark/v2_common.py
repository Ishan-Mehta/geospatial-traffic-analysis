"""
Shared helpers for the v2 benchmark scripts (1b, 4_v2, 4b_v2, 3_v2).

- small maths / text helpers (haversine, fuzzy name similarity, deterministic hash)
- API key loading and plain-language API error messages (never print keys)
- OsmNetwork: the local OSM drive graph in UTM metres — snapping, shortest paths,
  and map-matching a Google polyline onto OSM roads (names + road classes)
- tag helpers (distance band, road type) shared by Phase 1 (OSM path) and Phase 2 (Google path)
"""

import difflib
import hashlib
import json
import math
import os
import re
import sys
import time

import numpy as np

import config as C

LAT_LNG_CRS = "EPSG:4326"


# =====================================================================
#  Small helpers
# =====================================================================
def haversine_m(lat1, lng1, lat2, lng2):
    """Great-circle distance in metres (works on scalars or numpy arrays)."""
    r = 6371000.0
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dp = p2 - p1
    dl = np.radians(np.asarray(lng2) - np.asarray(lng1))
    a = np.sin(dp / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
    return 2 * r * np.arcsin(np.sqrt(a))


_STOP_TOKENS = {"bengaluru", "bangalore", "karnataka", "india", "the"}


def _tokens(s: str) -> list:
    s = re.sub(r"[^a-z0-9 ]+", " ", str(s).lower())
    return [t for t in s.split() if t and t not in _STOP_TOKENS]


def token_set_ratio(a: str, b: str) -> float:
    """0-100 similarity that ignores word order and extra words (fuzzywuzzy-style)."""
    ta, tb = set(_tokens(a)), set(_tokens(b))
    if not ta or not tb:
        return 0.0
    inter = " ".join(sorted(ta & tb))
    s_a = (inter + " " + " ".join(sorted(ta - tb))).strip()
    s_b = (inter + " " + " ".join(sorted(tb - ta))).strip()
    ratio = lambda x, y: difflib.SequenceMatcher(None, x, y).ratio() if x and y else 0.0
    return 100.0 * max(ratio(inter, s_a), ratio(inter, s_b), ratio(s_a, s_b))


def stable_hash(*parts) -> int:
    """Deterministic integer hash (Python's hash() is salted per process)."""
    return int(hashlib.md5("|".join(map(str, parts)).encode()).hexdigest()[:12], 16)


def sha1_short(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:12]


def load_env_key(name: str) -> str:
    """Read an API key from the project .env. Exits with a pointer to the billing guide if missing."""
    from dotenv import load_dotenv
    load_dotenv(C._PROJECT_ROOT / ".env")
    key = os.getenv(name)
    if not key:
        sys.exit(f"Error: {name} not found in .env (see docs/benchmark_v2/BILLING_AND_KEYS.md)")
    return key


def friendly_api_error(status: int, text: str) -> str:
    """Translate an API error into the row of BILLING_AND_KEYS.md §C. Never includes the key."""
    t = str(text).lower()
    if "billing" in t:
        return "Billing not enabled for this project -> BILLING_AND_KEYS.md A2/B2"
    if "has not been used" in t or "is disabled" in t or "service_disabled" in t:
        return "API not enabled in this project -> BILLING_AND_KEYS.md B1"
    if "not authorized" in t or "request_denied" in t:
        return "API key restriction blocks this API -> BILLING_AND_KEYS.md B3"
    if "api_key_invalid" in t or "api key not valid" in t:
        return "API key invalid -> re-copy key into .env"
    if status == 429 or "resource_exhausted" in t:
        return "Quota / rate limit reached -> wait or raise quota (BILLING_AND_KEYS.md A4/B4)"
    if status == 404 or "not_found" in t:
        return "Model / resource not found -> check model_name in config.py"
    return f"HTTP {status}: {str(text)[:300]}"


# Errors that will fail identically on every call -> stop the run instead of burning calls
FATAL_MARKERS = ("billing", "has not been used", "is disabled", "service_disabled", "not authorized",
                 "request_denied", "api_key_invalid", "api key not valid", "permission_denied")


def is_fatal_error(status: int, text: str) -> bool:
    t = str(text).lower()
    return status in (401, 403, 404) or any(m in t for m in FATAL_MARKERS)


def append_jsonl(path, record: dict):
    """Append one record and flush immediately (safe to interrupt and resume)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def read_jsonl(path) -> list:
    if not path.exists():
        return []
    out = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    pass          # a half-written last line after a crash is ignored
    return out


# =====================================================================
#  Tags shared by Phase 1 (OSM path) and Phase 2 (Google path) — METHODOLOGY §3
# =====================================================================
def band_of(length_m: float):
    for name, lo, hi in C.V2_BANDS:
        if lo <= length_m < hi:
            return name
    return None


def road_type_of(share: float) -> str:
    if share >= C.V2_ARTERIAL_MIN_SHARE:
        return "arterial"
    if share <= C.V2_SUBARTERIAL_MAX_SHARE:
        return "sub_arterial"
    return "mixed"


def edge_highway(d: dict):
    hw = d.get("highway")
    return hw[0] if isinstance(hw, list) else hw


def edge_names(d: dict) -> list:
    nm = d.get("name")
    return [n for n in (nm if isinstance(nm, list) else [nm]) if isinstance(n, str) and n]


def load_hotspot_union():
    """Buffered union (UTM) of hotspot legs, and the leg GeoDataFrame (UTM)."""
    import geopandas as gpd
    from shapely.ops import unary_union
    if not C.V2_HOTSPOT_LEGS_GEOJSON.exists():
        sys.exit("hotspot_legs.geojson missing — run `1b_build_od_pairs.py legs` first.")
    legs = gpd.read_file(C.V2_HOTSPOT_LEGS_GEOJSON).to_crs(C.UTM_CRS)
    hot = legs[legs.is_hotspot]
    return unary_union(hot.geometry.buffer(C.V2_HOTSPOT_BUFFER_M).tolist()), legs


# =====================================================================
#  OSM graph helpers (projected to UTM for metric distances)
# =====================================================================
class OsmNetwork:
    """Loads the local drive graph once; snapping, paths and map-matching in metres."""

    def __init__(self):
        import networkx as nx
        import osmnx as ox
        from pyproj import Transformer
        from shapely import STRtree
        from shapely.geometry import LineString, Point

        print(f"Loading OSM graph {C.OSM_GRAPH_PATH.name} (~40 s)...")
        t0 = time.time()
        self.G = ox.load_graphml(C.OSM_GRAPH_PATH)
        self.to_utm = Transformer.from_crs(LAT_LNG_CRS, C.UTM_CRS, always_xy=True)
        self.to_ll = Transformer.from_crs(C.UTM_CRS, LAT_LNG_CRS, always_xy=True)

        # Snap only to the largest strongly connected component, otherwise a landmark can
        # land on an isolated fragment (e.g. a one-way stub) from which nothing is reachable.
        nodes = list(max(nx.strongly_connected_components(self.G), key=len))
        xs = np.array([self.G.nodes[n]["x"] for n in nodes])
        ys = np.array([self.G.nodes[n]["y"] for n in nodes])
        ux, uy = self.to_utm.transform(xs, ys)
        self.node_ids = np.array(nodes)
        self.node_xy = {n: (x, y) for n, x, y in zip(nodes, ux, uy)}
        # all nodes (incl. small components) are still needed to draw path geometries
        for n, d in self.G.nodes(data=True):
            if n not in self.node_xy:
                self.node_xy[n] = self.to_utm.transform(d["x"], d["y"])
        self.node_tree = STRtree([Point(x, y) for x, y in zip(ux, uy)])
        self._edge_tree = None
        self._Point, self._LineString, self._STRtree = Point, LineString, STRtree
        print(f"  {self.G.number_of_nodes():,} nodes ({len(nodes):,} in largest strongly connected "
              f"component, used for snapping), {self.G.number_of_edges():,} edges in {time.time() - t0:.0f}s")

    def utm(self, lat, lng):
        return self.to_utm.transform(lng, lat)

    def nearest_node(self, lat, lng):
        x, y = self.utm(lat, lng)
        idx = self.node_tree.query_nearest(self._Point(x, y))[0]
        n = self.node_ids[idx]
        nx_, ny_ = self.node_xy[n]
        return n, math.hypot(x - nx_, y - ny_)

    def _build_edge_index(self):
        """One straight segment per (u, v) edge (the graph is unsimplified: a node at every bend)."""
        if self._edge_tree is not None:
            return
        lines, data = [], []
        for u, v, d in self.G.edges(data=True):
            if u == v:
                continue
            lines.append(self._LineString([self.node_xy[u], self.node_xy[v]]))
            data.append(d)
        self._edge_lines, self._edge_data = lines, data
        self._edge_tree = self._STRtree(lines)

    def nearest_edge_dist(self, lat, lng):
        """Distance (m) from a point to the nearest drivable edge."""
        self._build_edge_index()
        p = self._Point(*self.utm(lat, lng))
        idx = self._edge_tree.query_nearest(p)[0]
        return p.distance(self._edge_lines[idx])

    def best_edge(self, u, v):
        """Shortest parallel edge data between u and v."""
        data = self.G.get_edge_data(u, v)
        return min(data.values(), key=lambda d: float(d.get("length", 0)))

    def line_to_utm(self, coords_lnglat):
        xs, ys = self.to_utm.transform([c[0] for c in coords_lnglat], [c[1] for c in coords_lnglat])
        return self._LineString(list(zip(xs, ys)))

    def match_line(self, line_utm, step_m=None, max_dist_m=None) -> dict:
        """
        Map-match a route line (UTM) onto OSM edges.
        Samples a point every `step_m` metres, takes the nearest edge within `max_dist_m`.
        Returns ordered road names (consecutive duplicates collapsed), arterial share of the
        matched samples, and the unmatched fraction (a quality indicator).
        """
        step_m = step_m or C.V2_MATCH_STEP_M
        max_dist_m = max_dist_m or C.V2_MATCH_MAX_DIST_M
        self._build_edge_index()
        length = line_utm.length
        if length == 0:
            return {"road_names": [], "arterial_share": 0.0, "unmatched_frac": 1.0, "n_samples": 0}
        dists = np.arange(0, length, step_m)
        pts = [line_utm.interpolate(d) for d in dists]
        idx, dist = self._edge_tree.query_nearest(pts, return_distance=True, all_matches=False)
        # query_nearest returns [[input_idx...], [tree_idx...]]
        nearest = {int(i): (int(t), float(dd)) for i, t, dd in zip(idx[0], idx[1], dist)}
        runs, matched, arterial = [], 0, 0          # runs = [name, consecutive samples]
        for i in range(len(pts)):
            t, dd = nearest.get(i, (None, 1e9))
            if t is None or dd > max_dist_m:
                continue
            d = self._edge_data[t]
            matched += 1
            if edge_highway(d) in C.V2_ARTERIAL_HIGHWAYS:
                arterial += 1
            nm = (edge_names(d) or [None])[0]
            if runs and runs[-1][0] == nm:
                runs[-1][1] += 1
            else:
                runs.append([nm, 1])
        # Drop "flicker": names held for fewer than V2_MATCH_MIN_RUN samples (~60 m) — side streets touched at
        # junctions or parallel carriageways — then collapse consecutive duplicates.
        names = []
        for nm, k in runs:
            if nm and k >= C.V2_MATCH_MIN_RUN and (not names or names[-1] != nm):
                names.append(nm)
        return {"road_names": names,
                "arterial_share": arterial / matched if matched else 0.0,
                "unmatched_frac": 1 - matched / len(pts),
                "n_samples": len(pts)}


def basemap(ax, net):
    """Light grey primary/secondary road network as background (lat/lng axes)."""
    xs, ys = [], []
    for u, v, d in net.G.edges(data=True):
        if edge_highway(d) in ("motorway", "trunk", "primary", "secondary"):
            xs += [net.G.nodes[u]["x"], net.G.nodes[v]["x"], None]
            ys += [net.G.nodes[u]["y"], net.G.nodes[v]["y"], None]
    ax.plot(xs, ys, color="#cfcfcf", lw=0.4, zorder=0)
    ax.set_aspect(1 / math.cos(math.radians(12.97)))
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
