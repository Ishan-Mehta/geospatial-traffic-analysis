"""
Step 6 (v2) — report figures for the professor update (Phase 5). Offline, NO API calls.

  fig_A_routes_map.png      the 72 benchmark routes (Google's Wednesday-midday path) over Bangalore's main roads
  fig_B_time_by_slot.png    typical weekday travel time at each time of day: Google vs Gemini

Inputs: gmaps/gmaps_responses.jsonl, od_pairs.csv, results/comparison_<model>_A.csv, the OSM graph (basemap).
Output: docs/benchmark_v2/report/figures/. Colours: dataviz reference palette slots 1–2 (validated, CVD-safe).
Usage: python 6_report_figures_v2.py [--model KEY]
"""

import argparse
import json

import numpy as np
import pandas as pd

import config as C
from v2_common import read_jsonl

GOOGLE, GEMINI = "#2a78d6", "#eb6834"             # palette slots 1 (blue) and 2 (orange)
INK, INK2, GRID = "#0b0b0b", "#52514e", "#e4e3df"
SLOT_LABELS = {"AM_PEAK": "8 am", "MID_DAY": "2 pm", "PM_PEAK": "6 pm", "NIGHT": "11 pm"}


def style(plt):
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 11, "axes.edgecolor": GRID,
                         "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2,
                         "axes.spines.top": False, "axes.spines.right": False, "text.color": INK})


def fig_routes_map(out, plt):
    import osmnx as ox
    from v2_common import edge_highway
    G = ox.load_graphml(C.OSM_GRAPH_PATH)
    od = pd.read_csv(C.V2_OD_PAIRS_CSV)
    recs = [r for r in read_jsonl(C.V2_GMAPS_DIR / C.V2_GMAPS_RESPONSES_JSONL)
            if r.get("status") == "ok" and r["day"] == "Wednesday" and r["slot_id"] == "MID_DAY"]
    fig, ax = plt.subplots(figsize=(6.4, 6.4))
    for u, v, d in G.edges(data=True):
        hw = edge_highway(d)
        if hw in ("motorway", "trunk", "primary", "secondary"):
            ax.plot([G.nodes[u]["x"], G.nodes[v]["x"]], [G.nodes[u]["y"], G.nodes[v]["y"]],
                    color="#d9d8d3", lw=0.5 if hw == "secondary" else 0.9, zorder=0, solid_capstyle="round")
    for r in recs:
        xs, ys = zip(*r["routes"][0]["polyline"])
        ax.plot(xs, ys, color=GOOGLE, lw=1.4, alpha=0.75, zorder=1, solid_capstyle="round")
    pts = pd.concat([od[["origin_lat", "origin_lng"]].set_axis(["lat", "lng"], axis=1),
                     od[["dest_lat", "dest_lng"]].set_axis(["lat", "lng"], axis=1)]).drop_duplicates()
    ax.scatter(pts.lng, pts.lat, s=16, color="white", edgecolor=INK, linewidth=0.8, zorder=2)
    ax.set_aspect(1 / np.cos(np.radians(12.97)))
    ax.set_xticks([]), ax.set_yticks([])
    for s in ax.spines.values():
        s.set_visible(False)
    ax.set_title(f"{len(recs)} test routes between {len(pts)} Bangalore landmarks", fontsize=11, color=INK, loc="left")
    fig.savefig(out / "fig_A_routes_map.png", dpi=200, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def fig_time_by_slot(out, plt, model):
    c = pd.read_csv(C.V2_DIR / "results" / f"comparison_{model}_A.csv")
    c = c[(c.sample_idx == 0) & (~c.is_weekend)]
    slots = ["AM_PEAK", "MID_DAY", "PM_PEAK", "NIGHT"]
    g = c.groupby("slot_id").g_min.median().reindex(slots)
    l = c.groupby("slot_id").llm_min.median().reindex(slots)
    diff = c.groupby("slot_id").lr_time.median().reindex(slots).pipe(np.exp) - 1   # median of per-trip % gap
    x = np.arange(len(slots))
    w = 0.36
    fig, ax = plt.subplots(figsize=(6.6, 3.6))
    bg = ax.bar(x - w / 2 - 0.01, g.values, w, color=GOOGLE, label="Google Maps (predicted)", zorder=2)
    bl = ax.bar(x + w / 2 + 0.01, l.values, w, color=GEMINI, label="Gemini (no map access)", zorder=2)
    for rect in list(bg) + list(bl):                 # value labels in text ink
        ax.text(rect.get_x() + rect.get_width() / 2, rect.get_height() + 0.6, f"{rect.get_height():.0f}",
                ha="center", va="bottom", fontsize=9, color=INK2)
    for i, d in enumerate(diff.values):
        ax.text(x[i], max(g.values[i], l.values[i]) + 4.5, f"{d:+.0%}", ha="center", fontsize=10,
                color=INK, fontweight="bold")
    ax.set_xticks(x, [SLOT_LABELS[s] for s in slots])
    ax.set_ylabel("typical trip time (min)")
    ax.set_ylim(0, max(g.max(), l.max()) * 1.32)
    ax.yaxis.grid(True, color=GRID, lw=0.8, zorder=0)
    ax.set_axisbelow(True)
    ax.legend(frameon=False, loc="upper left", fontsize=9, ncol=2)
    ax.set_title("Weekday trip time by time of day (bold = Gemini vs Google)", fontsize=11, color=INK, loc="left")
    fig.savefig(out / "fig_B_time_by_slot.png", dpi=200, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return pd.DataFrame({"google_min": g.round(1), "gemini_min": l.round(1), "median_gap": diff.round(3)})


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", default=C.V2_ACTIVE_LLM)
    args = ap.parse_args()
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    style(plt)
    out = C._PROJECT_ROOT / "docs" / "benchmark_v2" / "report" / "figures"
    out.mkdir(parents=True, exist_ok=True)
    tbl = fig_time_by_slot(out, plt, args.model)
    print(tbl.to_string())
    fig_routes_map(out, plt)
    print(f"Figures -> {out}")


if __name__ == "__main__":
    main()
