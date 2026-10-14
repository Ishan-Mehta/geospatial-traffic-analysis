"""
Step 6 (v2) — report figures for the professor update (Phase 5). Offline, NO API calls.

  fig_A_routes_map.png      the 72 benchmark routes (Google's Wednesday-midday path) over Bangalore's main roads
  fig_B_time_by_slot.png    typical weekday travel time at each time of day: Google vs Gemini
  fig_C_day_shape.png       shape of the day: time relative to the same trip at weekday night (weekday | weekend)
  fig_D_rush_multiplier.png per-trip rush-hour multiplier (peak ÷ night), Gemini vs Google, by trip length
  fig_E_distance_time.png   every query: Gemini vs Google distance and time (log axes)
  fig_F_traffic_labels.png  Gemini's weekday traffic label by time of day, with Google's traffic index
  fig_G_google_heatmap.png  Google's traffic index by day and time of day

Inputs: gmaps/gmaps_responses.jsonl, od_pairs.csv, results/comparison_<model>_A.csv, the OSM graph (basemap).
Output: docs/benchmark_v2/report/figures/. Colours: dataviz reference palette slots 1–2 (validated, CVD-safe).
Usage: python 6_report_figures_v2.py [--model KEY] [--only B,C,...]
"""

import argparse
import json

import numpy as np
import pandas as pd

import config as C
from v2_common import read_jsonl

GOOGLE, GEMINI = "#2a78d6", "#eb6834"             # palette slots 1 (blue) and 2 (orange)
CAT3 = ["#2a78d6", "#eb6834", "#1baf7a"]           # palette slots 1-3 (validated all-pairs) for 3 categories
SEQ = ["#cde2fb", "#86b6ef", "#2a78d6", "#104281"] # sequential blue steps 100/250/450/650 (none→heavy)
SLOTS = ["AM_PEAK", "MID_DAY", "PM_PEAK", "NIGHT"]
BANDS = {"B1_1-5km": "1–5 km", "B2_5-12km": "5–12 km", "B3_12-25km": "12–29 km"}
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


def _comparison(model):
    c = pd.read_csv(C.V2_DIR / "results" / f"comparison_{model}_A.csv")
    return c[c.sample_idx == 0].copy()


def _finish(ax, title):
    ax.yaxis.grid(True, color=GRID, lw=0.8, zorder=0)
    ax.set_axisbelow(True)
    ax.set_title(title, fontsize=11, color=INK, loc="left")


def fig_day_shape(out, plt, model):
    """Each trip's time ÷ the same trip's weekday-night time (mean of weekday 23:00), median over trips."""
    c = _comparison(model)
    wk_night = c[(~c.is_weekend) & (c.slot_id == "NIGHT")]
    rows = {}
    for src, col in (("google", "g_min"), ("gemini", "llm_min")):
        ref = wk_night.groupby("route_id")[col].mean()
        c[f"{src}_rel"] = c[col] / c.route_id.map(ref)
    fig, axes = plt.subplots(1, 2, figsize=(8.2, 3.5), sharey=True)
    x = np.arange(4)
    for ax, wkend, name in ((axes[0], False, "Weekdays"), (axes[1], True, "Weekends")):
        d = c[c.is_weekend == wkend].groupby("slot_id")[["google_rel", "gemini_rel"]].median().reindex(SLOTS)
        rows[name] = d.round(2)
        for col, colr, lab, mk in (("google_rel", GOOGLE, "Google Maps", "o"), ("gemini_rel", GEMINI, "Gemini", "s")):
            ax.plot(x, d[col].values, color=colr, lw=2, marker=mk, ms=8, mec="white", mew=2, zorder=3, label=lab)
            for xi, v, sl in zip(x, d[col].values, SLOTS):
                if sl == "NIGHT":                      # both lines meet near 1.0: label beside the point
                    ax.text(xi + 0.12, v + (0.06 if col == "gemini_rel" else -0.1), f"{v:.2f}", ha="left",
                            fontsize=9, color=INK2)
                else:
                    ax.text(xi, v + (0.08 if col == "gemini_rel" else -0.15), f"{v:.2f}", ha="center",
                            fontsize=9, color=INK2)
        ax.axhline(1, color=INK2, lw=0.8, ls=":", zorder=1)
        ax.set_xticks(x, [SLOT_LABELS[s] for s in SLOTS])
        _finish(ax, name)
    axes[0].set_ylabel("times longer than the same trip\nat weekday night")
    axes[0].set_ylim(0.7, 2.6)
    axes[0].set_xlim(-0.3, 3.6)
    axes[0].legend(frameon=False, loc="upper left", fontsize=9)
    fig.tight_layout()
    fig.savefig(out / "fig_C_day_shape.png", dpi=200, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return rows


def fig_rush_multiplier(out, plt, model):
    r = pd.read_csv(C.V2_DIR / "results" / f"route_metrics_{model}_A.csv")
    c = _comparison(model).drop_duplicates("route_id").set_index("route_id")
    r = r.join(c[["origin_name", "dest_name", "band_google"]], on="route_id")
    fig, ax = plt.subplots(figsize=(5.6, 4.6))
    lim = (0.85, 3.25)
    ax.plot(lim, lim, color=INK2, lw=0.8, ls=":", zorder=1)
    ax.text(2.55, 2.42, "Gemini = Google", rotation=38, fontsize=8.5, color=INK2)
    for (band, lab), colr in zip(BANDS.items(), CAT3):
        g = r[r.band_google == band]
        ax.scatter(g.pn_google, g.pn_llm, s=46, color=colr, edgecolor="white", linewidth=1.2, zorder=3,
                   label=f"{lab} trips (Gemini median {g.pn_llm.median():.2f}, Google {g.pn_google.median():.2f})")
    o = r.loc[r.pn_google.idxmin()]
    ax.annotate(f"{o.origin_name} → {o.dest_name}:\nGoogle says night is slower", (o.pn_google, o.pn_llm),
                xytext=(0.9, 1.4), fontsize=8, color=INK2, va="top",
                arrowprops=dict(arrowstyle="-", color=INK2, lw=0.7, relpos=(0.03, 1)))
    ax.set_xlim(lim), ax.set_ylim(lim)
    ax.set_xlabel("Google: rush-hour time ÷ night time")
    ax.set_ylabel("Gemini: rush-hour time ÷ night time")
    ax.legend(frameon=False, loc="upper right", fontsize=7.5, handletextpad=0.2)
    above = int((r.pn_llm > r.pn_google).sum())
    _finish(ax, f"Rush-hour slowdown per trip (weekdays): Gemini higher on {above} of {len(r)}")
    ax.xaxis.grid(True, color=GRID, lw=0.8, zorder=0)
    fig.savefig(out / "fig_D_rush_multiplier.png", dpi=200, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def fig_distance_time(out, plt, model):
    c = _comparison(model)
    fig, axes = plt.subplots(1, 2, figsize=(8.6, 4.1))
    groups = [("rush hours (8 am, 6 pm)", c.slot_id.isin(["AM_PEAK", "PM_PEAK"])),
              ("2 pm", c.slot_id == "MID_DAY"), ("11 pm", c.slot_id == "NIGHT")]
    for ax, gx, lx, unit, title in ((axes[0], "g_km", "llm_km", "km", "Distance"),
                                    (axes[1], "g_min", "llm_min", "min", "Time")):
        lo = min(c[gx].min(), c[lx].min()) * 0.8
        hi = max(c[gx].max(), c[lx].max()) * 1.2
        ax.plot((lo, hi), (lo, hi), color=INK2, lw=0.8, ls=":", zorder=1)
        if title == "Distance":
            ax.scatter(c[gx], c[lx], s=10, color=GOOGLE, alpha=0.35, linewidth=0, zorder=2)
        else:
            for (lab, m), colr in zip(groups, [GEMINI, CAT3[2], GOOGLE]):
                ax.scatter(c.loc[m, gx], c.loc[m, lx], s=10, color=colr, alpha=0.4, linewidth=0, zorder=2, label=lab)
            ax.legend(frameon=False, loc="upper left", fontsize=8, markerscale=2)
        ax.set_xscale("log"), ax.set_yscale("log")
        ax.set_xlim(lo, hi), ax.set_ylim(lo, hi)
        ticks = [t for t in (1, 2, 5, 10, 20, 50, 100) if lo <= t <= hi]
        ax.set_xticks(ticks, [str(t) for t in ticks]), ax.set_yticks(ticks, [str(t) for t in ticks])
        ax.minorticks_off()
        ax.set_xlabel(f"Google ({unit})"), ax.set_ylabel(f"Gemini ({unit})")
        med = np.exp(c[f"lr_{'dist' if title == 'Distance' else 'time'}"].median()) - 1
        _finish(ax, f"{title}: typically {med:+.0%} vs Google")
        ax.xaxis.grid(True, color=GRID, lw=0.8, zorder=0)
    fig.tight_layout()
    fig.savefig(out / "fig_E_distance_time.png", dpi=200, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def fig_traffic_labels(out, plt, model):
    c = _comparison(model)
    c = c[~c.is_weekend]
    order = ["none", "light", "moderate", "heavy"]
    share = (c.groupby("slot_id").llm_label.value_counts(normalize=True).unstack(fill_value=0)
             .reindex(index=SLOTS, columns=order, fill_value=0))
    gidx = c.groupby("slot_id").traffic_index.median().reindex(SLOTS)
    fig, ax = plt.subplots(figsize=(6.6, 3.7))
    x = np.arange(4)
    bottom = np.zeros(4)
    for lab, colr in zip(order, SEQ):
        v = share[lab].values
        ax.bar(x, v, 0.6, bottom=bottom, color=colr, edgecolor="white", linewidth=2, zorder=2, label=f"“{lab}”")
        for xi, vi, bi in zip(x, v, bottom):
            if vi >= 0.07:
                ax.text(xi, bi + vi / 2, f"{vi:.0%}", ha="center", va="center", fontsize=9,
                        color="white" if lab in ("moderate", "heavy") else INK)
        bottom += v
    for xi, gi in zip(x, gidx.values):
        ax.text(xi, 1.04, f"Google: {gi - 1:+.0%}", ha="center", fontsize=9, color=INK)
    ax.set_xticks(x, [SLOT_LABELS[s] for s in SLOTS])
    ax.set_yticks([0, 0.5, 1], ["0%", "50%", "100%"])
    ax.set_ylim(0, 1.13)
    ax.set_ylabel("share of Gemini's answers")
    ax.legend(frameon=False, loc="center left", bbox_to_anchor=(1.0, 0.5), fontsize=9, title="Gemini said",
              title_fontsize=9)
    _finish(ax, "Weekdays: Gemini's traffic label vs Google's slowdown")
    fig.savefig(out / "fig_F_traffic_labels.png", dpi=200, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return share.round(3), gidx.round(3)


def fig_google_heatmap(out, plt):
    from matplotlib.colors import LinearSegmentedColormap
    q = pd.read_csv(C.V2_GMAPS_DIR / "gmaps_queries.csv")
    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    piv = q.pivot_table(values="traffic_index", index="slot_id", columns="day", aggfunc="median").reindex(
        index=SLOTS, columns=days)
    cmap = LinearSegmentedColormap.from_list("blue", ["#cde2fb", "#2a78d6", "#104281"])
    fig, ax = plt.subplots(figsize=(6.8, 2.9))
    ax.imshow(piv.values, cmap=cmap, vmin=1.0, vmax=1.65, aspect="auto")
    for i in range(4):
        for j in range(7):
            v = piv.values[i, j]
            ax.text(j, i, f"{v - 1:+.0%}", ha="center", va="center", fontsize=9, color="white" if v > 1.3 else INK)
    ax.set_xticks(range(7), [d[:3] + ("\n(holiday)" if d == "Saturday" else "") for d in days])
    ax.set_yticks(range(4), [SLOT_LABELS[s] for s in SLOTS])
    for s in ax.spines.values():
        s.set_visible(False)
    ax.tick_params(length=0)
    ax.set_title("Google: how much slower than the trip's best time (typical trip)", fontsize=11, color=INK, loc="left")
    fig.savefig(out / "fig_G_google_heatmap.png", dpi=200, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return piv.round(2)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", default=C.V2_ACTIVE_LLM)
    ap.add_argument("--only", default="A,B,C,D,E,F,G", help="comma list of figure letters (A needs osmnx)")
    args = ap.parse_args()
    which = set(args.only.upper().split(","))
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    style(plt)
    out = C._PROJECT_ROOT / "docs" / "benchmark_v2" / "report" / "figures"
    out.mkdir(parents=True, exist_ok=True)
    if "B" in which:
        print(fig_time_by_slot(out, plt, args.model).to_string())
    if "C" in which:
        for k, v in fig_day_shape(out, plt, args.model).items():
            print(k, v.to_dict())
    if "D" in which:
        fig_rush_multiplier(out, plt, args.model)
    if "E" in which:
        fig_distance_time(out, plt, args.model)
    if "F" in which:
        sh, gi = fig_traffic_labels(out, plt, args.model)
        print(sh.to_string()); print(gi.to_dict())
    if "G" in which:
        print(fig_google_heatmap(out, plt).to_string())
    if "A" in which:
        fig_routes_map(out, plt)
    print(f"Figures -> {out}")


if __name__ == "__main__":
    main()
