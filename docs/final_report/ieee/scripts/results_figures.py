"""Results figures for the report: Google Maps against Gemini and ChatGPT (neutral prompt).
Reads aggregate result tables only.

Usage: python results_figures.py <project_root> <output dir>
"""
import sys
import numpy as np, pandas as pd
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt

R, OUT = sys.argv[1], sys.argv[2]
RES = f"{R}/data/benchmark_round2/results"
plt.rcParams.update({"font.family": "serif", "font.serif": ["Times New Roman", "Nimbus Roman", "DejaVu Serif"],
                     "font.size": 8, "axes.spines.top": False, "axes.spines.right": False, "axes.edgecolor": "#555",
                     "axes.linewidth": 0.6, "xtick.major.width": 0.6, "ytick.major.width": 0.6, "legend.frameon": False})
G, GREY = "#2a78d6", "#9a9a9a"
MODELS = [("gemini_38_flash", "Gemini", "#eb6834", "#f3b393", "s"), ("openai_main", "ChatGPT", "#1baf7a", "#a3dcc6", "^")]
SLOTS = ["AM_PEAK", "MID_DAY", "PM_PEAK", "NIGHT"]; SLAB = ["08:00", "14:00", "18:00", "23:00"]
DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
BANDS = ["B1_1-5km", "B2_5-12km", "B3_12-25km"]; BLAB = ["1–5 km", "5–12 km", "12 km+"]

D, RM, TOD = {}, {}, {}
for key, *_ in MODELS:
    d = pd.read_csv(f"{RES}/{key}/comparison_{key}_A.csv"); D[key] = d[d.sample_idx == 0]
    RM[key] = pd.read_csv(f"{RES}/{key}/route_metrics_{key}_A.csv")
    TOD[key] = pd.read_csv(f"{RES}/{key}/summary_time_of_day.csv")
d0 = D["gemini_38_flash"]


def grid(a, axis="y"):
    a.grid(axis=axis, color="#e4e3df", lw=0.5); a.set_axisbelow(True)


def save(fig, name):
    fig.savefig(f"{OUT}/{name}"); plt.close(fig); print("saved", name)


# 1. Google traffic index heatmap: day x time (Google only)
h = d0.groupby(["slot_id", "day"]).traffic_index.median().unstack().reindex(index=SLOTS, columns=DAYS)
fig, ax = plt.subplots(figsize=(3.5, 1.45))
ax.imshow(h.values, cmap="Blues", vmin=1.0, vmax=1.8, aspect="auto")
for i in range(4):
    for j in range(7):
        v = h.values[i, j]
        ax.text(j, i, f"+{(v - 1) * 100:.0f}%", ha="center", va="center", fontsize=7, color="white" if v > 1.45 else "#222")
ax.set_xticks(range(7)); ax.set_xticklabels([x[:3] for x in DAYS]); ax.set_yticks(range(4)); ax.set_yticklabels(SLAB)
ax.tick_params(length=0)
for s in ax.spines.values(): s.set_visible(False)
fig.tight_layout(pad=0.2); save(fig, "fig_google_heatmap.pdf")

# 2. Landmark check: distance between each LLM's point and Google's
GR = {"gemini_38_flash": f"{R}/data/benchmark_v2/llm/gemini_38_flash_grounding_results.csv",
      "openai_main": f"{R}/data/benchmark_round2/llm/openai_main_grounding_results.csv"}
fig, ax = plt.subplots(figsize=(3.5, 1.4))
bins = np.logspace(np.log10(0.01), np.log10(20), 24)
for key, lab, c, cl, mk in MODELS:
    gr = pd.read_csv(GR[key]); e = gr.error_m.clip(lower=10) / 1000
    ax.hist(e, bins=bins, color=c, alpha=0.55 if key == "openai_main" else 0.8, edgecolor="white", lw=0.3,
            label=f"{lab} (median {gr.error_m.median() / 1000:.2f} km)")
    print("  landmarks", lab, len(gr), "median km", round(e.median(), 3), "over 2 km", int((gr.error_m > 2000).sum()),
          "misplaced", int(gr.misplaced.sum()))
ax.set_xscale("log"); ax.axvline(2, color="#333", lw=0.7, ls="--")
ax.text(2.15, ax.get_ylim()[1] * 0.95, "2 km", fontsize=7, va="top")
ax.set_xticks([0.01, 0.1, 1, 10]); ax.set_xticklabels(["0.01", "0.1", "1", "10"])
ax.set_xlabel("Distance from Google's point (km)"); ax.set_ylabel("Landmarks"); grid(ax)
ax.legend(fontsize=6.5, loc="upper left")
fig.tight_layout(pad=0.3); save(fig, "fig_landmark_error.pdf")

# 3. Scatter: each LLM against Google, distance and time (rows = models)
SC = {"AM_PEAK": "#c0392b", "PM_PEAK": "#c0392b", "MID_DAY": "#9a9a9a", "NIGHT": "#1d3f73"}
fig, axs = plt.subplots(2, 2, figsize=(3.5, 3.25))
for row, (key, lab, c, cl, mk) in enumerate(MODELS):
    d = D[key]
    axs[row, 0].scatter(d.g_km, d.llm_km, s=1.2, color=c, alpha=0.45, lw=0)
    for sl in ["MID_DAY", "NIGHT", "AM_PEAK", "PM_PEAK"]:
        s = d[d.slot_id == sl]; axs[row, 1].scatter(s.g_min, s.llm_min, s=1.2, color=SC[sl], alpha=0.4, lw=0)
    for col, (lo, hi, t) in enumerate(((0.8, 50, "distance, km"), (3, 150, "time, min"))):
        a = axs[row, col]
        a.set_xscale("log"); a.set_yscale("log"); a.plot([lo, hi], [lo, hi], color="#333", lw=0.6, ls=":")
        a.set_xlim(lo, hi); a.set_ylim(lo, hi); a.set_aspect("equal"); a.minorticks_off()
        tk = [1, 3, 10, 30] if lo < 1 else [3, 10, 30, 100]
        a.set_xticks(tk); a.set_xticklabels([str(v) for v in tk]); a.set_yticks(tk); a.set_yticklabels([str(v) for v in tk])
        a.set_title(f"({'abcd'[row * 2 + col]}) {lab}, {t}", fontsize=7.5)
        if row == 1: a.set_xlabel("Google")
    axs[row, 0].set_ylabel(lab)
for lab, c in (("08:00, 18:00", "#c0392b"), ("14:00", "#9a9a9a"), ("23:00", "#1d3f73")):
    axs[0, 1].scatter([], [], s=6, color=c, label=lab)
axs[0, 1].legend(fontsize=6, loc="upper left", handletextpad=0.1, borderaxespad=0.1)
fig.tight_layout(pad=0.3, w_pad=0.5, h_pad=0.6); save(fig, "fig_scatter.pdf")

# 4. Shape of the day (relative to the same trip at weekday 23:00)
fig, ax = plt.subplots(1, 2, figsize=(3.5, 1.65), sharey=True)
for a, dt, t in ((ax[0], "weekday", "(a) Weekdays"), (ax[1], "weekend", "(b) Weekends")):
    gs = TOD["gemini_38_flash"][TOD["gemini_38_flash"].day_type == dt].set_index("slot_id").reindex(SLOTS)
    a.plot(range(4), gs.google_rel_night, color=G, marker="o", ms=2.6, lw=1.1, label="Google")
    for key, lab, c, cl, mk in MODELS:
        s = TOD[key][TOD[key].day_type == dt].set_index("slot_id").reindex(SLOTS)
        a.plot(range(4), s.llm_rel_night, color=c, marker=mk, ms=2.6, lw=1.1, label=lab)
    a.axhline(1, color=GREY, lw=0.6, ls=":"); a.set_xticks(range(4)); a.set_xticklabels(SLAB)
    a.set_title(t, fontsize=8); grid(a); a.set_ylim(0.7, 3.0)
ax[0].set_ylabel("Times the 23:00 trip"); ax[0].legend(fontsize=6.5, loc="upper left")
fig.tight_layout(pad=0.3, w_pad=0.6); save(fig, "fig_day_shape.pdf")

# 5. Rush-hour multiplier per route, both models
fig, ax = plt.subplots(figsize=(3.5, 2.0))
for key, lab, c, cl, mk in MODELS:
    rm = RM[key]
    ax.scatter(rm.pn_google, rm.pn_llm, s=9, color=c, marker=mk, lw=0, alpha=0.85,
               label=f"{lab} (median {rm.pn_llm.median():.2f})")
ax.plot([0.8, 3.4], [0.8, 3.4], color="#333", lw=0.6, ls=":"); ax.text(2.6, 2.45, "equal", fontsize=7, rotation=33)
o = RM["gemini_38_flash"].sort_values("pn_google").iloc[0]
ax.annotate("Yeshwanthpur Metro →\nPeenya Metro", (o.pn_google, o.pn_llm), xytext=(1.05, 1.0), fontsize=6.5,
            arrowprops=dict(arrowstyle="-", lw=0.5, color="#555"))
ax.set_xlim(0.8, 3.4); ax.set_ylim(0.8, 3.4); ax.set_xlabel("Google rush-hour multiplier (median 1.34)")
ax.set_ylabel("LLM rush-hour multiplier"); ax.legend(fontsize=6.5, loc="lower right"); grid(ax, "both")
fig.tight_layout(pad=0.3); save(fig, "fig_multiplier.pdf")

# 6. Traffic levels reported by each LLM on weekdays, with Google's traffic index
lev = ["none", "light", "moderate", "heavy"]; lc = ["#e8e8e8", "#bcd3ee", "#5b8fd1", "#1d3f73"]
fig, ax = plt.subplots(figsize=(3.5, 1.8))
w = 0.36
for k, (key, lab, c, cl, mk) in enumerate(MODELS):
    wk = D[key][D[key].day_type == "weekday"]
    sh = wk.groupby("slot_id").llm_label.value_counts(normalize=True).unstack().reindex(index=SLOTS, columns=lev).fillna(0)
    x = np.arange(4) + (k - 0.5) * (w + 0.04); bottom = np.zeros(4)
    for l, col in zip(lev, lc):
        ax.bar(x, sh[l] * 100, bottom=bottom, color=col, width=w, edgecolor="white", lw=0.3,
               label=l.capitalize() if k == 0 else None)
        bottom += sh[l].values * 100
    for xi in x:
        ax.text(xi, -9, lab[0], ha="center", fontsize=6.5)
gi = TOD["gemini_38_flash"][TOD["gemini_38_flash"].day_type == "weekday"].set_index("slot_id").reindex(SLOTS).google_traffic_index
for i, v in enumerate(gi):
    ax.text(i, 103, f"Google +{(v - 1) * 100:.0f}%", ha="center", fontsize=6.5)
ax.set_xticks(range(4)); ax.set_xticklabels(SLAB); ax.tick_params(axis="x", pad=9)
ax.set_ylim(0, 112); ax.set_ylabel("Share of answers (%)")
ax.legend(fontsize=6.5, loc="center left", bbox_to_anchor=(1.0, 0.5), handlelength=1)
fig.tight_layout(pad=0.3); save(fig, "fig_traffic_levels.pdf")

# 7. Where the LLMs do worst: typical miss (median % error per route) by route length
fig, ax = plt.subplots(1, 2, figsize=(3.5, 1.7), sharey=True)
x = np.arange(3); w = 0.36
for a, m, t in ((ax[0], "med_ape_time", "(a) Time"), (ax[1], "med_ape_dist", "(b) Distance")):
    for k, (key, lab, c, cl, mk) in enumerate(MODELS):
        v = [RM[key][RM[key].band == b][m].median() * 100 for b in BANDS]
        xs = x + (k - 0.5) * w
        a.bar(xs, v, w, color=c, label=lab)
        for xi, vi in zip(xs, v):
            a.text(xi, vi + 1, f"{vi:.0f}", ha="center", fontsize=6.5)
        print(" ", t, lab, [round(vi, 1) for vi in v])
    a.set_xticks(x); a.set_xticklabels(BLAB); a.set_title(t, fontsize=8); grid(a)
ax[0].set_ylabel("Typical miss (%)"); ax[1].legend(fontsize=7, loc="upper right")
fig.tight_layout(pad=0.3, w_pad=0.6); save(fig, "fig_where_worst.pdf")

# 8. Prompt wording and answer format: weekday typical time on the 10 repeat routes
cr = pd.read_csv(f"{R}/data/benchmark_v2/consistency_routes.csv").route_id
gw = d0[(d0.route_id.isin(cr)) & (d0.day_type == "weekday")].groupby("slot_id").g_min.median().reindex(SLOTS)
fig, ax = plt.subplots(figsize=(3.5, 1.75))
pe = pd.read_csv(f"{RES}/gemini_38_flash/summary_prompt_effect.csv"); pe = pe[pe.subset == "10 repeat routes"].set_index("version")
pc = pd.read_csv(f"{RES}/openai_main/summary_prompt_effect.csv"); pc = pc[pc.subset == "10 repeat routes"].set_index("version")
series = [(pe, "round1", "Gemini, earlier prompt", "#8e44ad", "v"),
          (pe, "control", "Gemini, neutral, whole route", "#f3b393", "s"),
          (pe, "round2", "Gemini, neutral, road by road", "#eb6834", "s"),
          (pc, "control", "ChatGPT, neutral, whole route", "#a3dcc6", "^"),
          (pc, "round2", "ChatGPT, neutral, road by road", "#1baf7a", "^")]
for tab, v, lab, c, mk in series:
    ax.plot(range(4), [tab.loc[v, f"weekday_min_{s}"] for s in SLOTS], color=c, marker=mk, ms=2.6, lw=1.0, label=lab)
ax.plot(range(4), gw.values, color=G, marker="o", ms=2.6, lw=1.0, ls="--", label="Google")
ax.set_xticks(range(4)); ax.set_xticklabels(SLAB); ax.set_ylabel("Typical weekday time (min)"); grid(ax)
ax.legend(fontsize=6, loc="center left", bbox_to_anchor=(1.0, 0.5), handlelength=1.5)
fig.tight_layout(pad=0.3); save(fig, "fig_prompt_effect.pdf")
print("  google 10 routes weekday", gw.round(1).tolist())
