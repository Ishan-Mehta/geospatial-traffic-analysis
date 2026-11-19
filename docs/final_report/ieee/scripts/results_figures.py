"""Results figures for the report (Google Maps vs Gemini, neutral prompt). Reads aggregate result tables only.

Usage: python results_figures.py <project_root> <output dir>
"""
import sys
import numpy as np, pandas as pd
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt

R, OUT = sys.argv[1], sys.argv[2]
RES = f"{R}/data/benchmark_round2/results/gemini_38_flash"
plt.rcParams.update({"font.family": "serif", "font.serif": ["Times New Roman", "Nimbus Roman", "DejaVu Serif"],
                     "font.size": 8, "axes.spines.top": False, "axes.spines.right": False, "axes.edgecolor": "#555",
                     "axes.linewidth": 0.6, "xtick.major.width": 0.6, "ytick.major.width": 0.6, "legend.frameon": False})
G, M, GREEN, GREY = "#2a78d6", "#eb6834", "#1baf7a", "#9a9a9a"
SLOTS = ["AM_PEAK", "MID_DAY", "PM_PEAK", "NIGHT"]; SLAB = ["08:00", "14:00", "18:00", "23:00"]
DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
BANDS = ["B1_1-5km", "B2_5-12km", "B3_12-25km"]; BLAB = ["1–5 km", "5–12 km", "12 km+"]

d = pd.read_csv(f"{RES}/comparison_gemini_38_flash_A.csv"); d = d[d.sample_idx == 0]
rm = pd.read_csv(f"{RES}/route_metrics_gemini_38_flash_A.csv")
tod = pd.read_csv(f"{RES}/summary_time_of_day.csv")


def grid(a, axis="y"):
    a.grid(axis=axis, color="#e4e3df", lw=0.5); a.set_axisbelow(True)


def save(fig, name):
    fig.savefig(f"{OUT}/{name}"); plt.close(fig); print("saved", name)


# 1. Google traffic index heatmap: day x time
h = d.groupby(["slot_id", "day"]).traffic_index.median().unstack().reindex(index=SLOTS, columns=DAYS)
fig, ax = plt.subplots(figsize=(3.5, 1.45))
ax.imshow(h.values, cmap="Blues", vmin=1.0, vmax=1.8, aspect="auto")
for i in range(4):
    for j in range(7):
        v = h.values[i, j]
        ax.text(j, i, f"+{(v - 1) * 100:.0f}%", ha="center", va="center", fontsize=7,
                color="white" if v > 1.45 else "#222")
ax.set_xticks(range(7)); ax.set_xticklabels([x[:3] for x in DAYS]); ax.set_yticks(range(4)); ax.set_yticklabels(SLAB)
ax.tick_params(length=0)
for s in ax.spines.values(): s.set_visible(False)
fig.tight_layout(pad=0.2); save(fig, "fig_google_heatmap.pdf")

# 2. Landmark check: distance between Gemini's point and Google's
gr = pd.read_csv(f"{R}/data/benchmark_v2/llm/gemini_38_flash_grounding_results.csv")
e = gr.error_m.clip(lower=10) / 1000
fig, ax = plt.subplots(figsize=(3.5, 1.35))
bins = np.logspace(np.log10(0.01), np.log10(max(20, e.max() * 1.1)), 22)
ax.hist(e, bins=bins, color=M, edgecolor="white", lw=0.3)
ax.set_xscale("log"); ax.axvline(2, color="#333", lw=0.7, ls="--")
ax.text(2.15, ax.get_ylim()[1] * 0.92, "2 km", fontsize=7, va="top")
ax.set_xticks([0.01, 0.1, 1, 10]); ax.set_xticklabels(["0.01", "0.1", "1", "10"])
ax.set_xlabel("Distance from Google's point (km)"); ax.set_ylabel("Landmarks"); grid(ax)
fig.tight_layout(pad=0.3); save(fig, "fig_landmark_error.pdf")
print("  landmarks", len(gr), "median km", round(e.median(), 2), "over 2 km", int((gr.error_m > 2000).sum()),
      "misplaced", int(gr.misplaced.sum()))

# 3. Scatter: Gemini vs Google, distance and time
fig, ax = plt.subplots(1, 2, figsize=(3.5, 1.85))
ax[0].scatter(d.g_km, d.llm_km, s=1.5, color=GREY, alpha=0.5, lw=0)
cols = {"AM_PEAK": M, "PM_PEAK": M, "MID_DAY": GREEN, "NIGHT": G}
for sl in ["MID_DAY", "NIGHT", "AM_PEAK", "PM_PEAK"]:
    s = d[d.slot_id == sl]; ax[1].scatter(s.g_min, s.llm_min, s=1.5, color=cols[sl], alpha=0.45, lw=0)
for a, lo, hi, t in ((ax[0], 0.8, 50, "(a) Distance, km"), (ax[1], 3, 150, "(b) Time, min")):
    a.set_xscale("log"); a.set_yscale("log"); a.plot([lo, hi], [lo, hi], color="#333", lw=0.6, ls=":")
    a.set_xlim(lo, hi); a.set_ylim(lo, hi); a.set_title(t, fontsize=8); a.set_xlabel("Google"); a.set_aspect("equal")
    tk = [1, 3, 10, 30] if lo < 1 else [3, 10, 30, 100]
    a.set_xticks(tk); a.set_xticklabels([str(v) for v in tk]); a.set_yticks(tk); a.set_yticklabels([str(v) for v in tk])
    a.minorticks_off()
ax[0].set_ylabel("Gemini")
for lab, c in (("08:00, 18:00", M), ("14:00", GREEN), ("23:00", G)):
    ax[1].scatter([], [], s=6, color=c, label=lab)
ax[1].legend(fontsize=6, loc="upper left", handletextpad=0.1, borderaxespad=0.1)
fig.tight_layout(pad=0.3, w_pad=0.6); save(fig, "fig_scatter.pdf")

# 4. Shape of the day (relative to the same trip at weekday 23:00)
fig, ax = plt.subplots(1, 2, figsize=(3.5, 1.6), sharey=True)
for a, dt, t in ((ax[0], "weekday", "(a) Weekdays"), (ax[1], "weekend", "(b) Weekends")):
    s = tod[tod.day_type == dt].set_index("slot_id").reindex(SLOTS)
    a.plot(range(4), s.google_rel_night, color=G, marker="o", ms=2.8, lw=1.1, label="Google")
    a.plot(range(4), s.llm_rel_night, color=M, marker="s", ms=2.8, lw=1.1, label="Gemini")
    for i, (gv, lv) in list(enumerate(zip(s.google_rel_night, s.llm_rel_night)))[:3]:
        a.text(i, lv + 0.08, f"{lv:.2f}", ha="center", fontsize=6, color=M)
        a.text(i, gv - 0.2, f"{gv:.2f}", ha="center", fontsize=6, color=G)
    a.axhline(1, color=GREY, lw=0.6, ls=":"); a.set_xticks(range(4)); a.set_xticklabels(SLAB)
    a.set_title(t, fontsize=8); grid(a); a.set_ylim(0.7, 3.0)
ax[0].set_ylabel("Times the 23:00 trip"); ax[0].legend(fontsize=7, loc="upper left")
fig.tight_layout(pad=0.3, w_pad=0.6); save(fig, "fig_day_shape.pdf")

# 5. Rush-hour multiplier per route
fig, ax = plt.subplots(figsize=(3.5, 2.0))
for b, lab, c, mk in zip(BANDS, BLAB, (M, G, GREEN), ("o", "s", "^")):
    s = rm[rm.band == b]; ax.scatter(s.pn_google, s.pn_llm, s=9, color=c, marker=mk, lw=0, label=lab)
ax.plot([0.8, 3.4], [0.8, 3.4], color="#333", lw=0.6, ls=":"); ax.text(2.55, 2.4, "equal", fontsize=7, rotation=33)
o = rm.sort_values("pn_google").iloc[0]
ax.annotate("Yeshwanthpur Metro →\nPeenya Metro", (o.pn_google, o.pn_llm), xytext=(1.25, 1.2), fontsize=6.5,
            arrowprops=dict(arrowstyle="-", lw=0.5, color="#555"))
ax.set_xlim(0.8, 3.4); ax.set_ylim(0.8, 3.4); ax.set_xlabel("Google rush-hour multiplier")
ax.set_ylabel("Gemini rush-hour multiplier"); ax.legend(fontsize=7, loc="lower right"); grid(ax, "both")
fig.tight_layout(pad=0.3); save(fig, "fig_multiplier.pdf")
print("  outlier", o.route_id, round(o.pn_google, 2), round(o.pn_llm, 2))

# 6. Traffic levels reported by Gemini, weekdays, with Google's traffic index
wk = d[d.day_type == "weekday"]
lev = ["none", "light", "moderate", "heavy"]; lc = ["#e8e8e8", "#bcd3ee", "#5b8fd1", "#1d3f73"]
sh = wk.groupby("slot_id").llm_label.value_counts(normalize=True).unstack().reindex(index=SLOTS, columns=lev).fillna(0)
fig, ax = plt.subplots(figsize=(3.5, 1.7))
bottom = np.zeros(4)
for l, c in zip(lev, lc):
    ax.bar(range(4), sh[l] * 100, bottom=bottom, color=c, width=0.6, label=l.capitalize(), edgecolor="white", lw=0.3)
    bottom += sh[l].values * 100
gi = tod[tod.day_type == "weekday"].set_index("slot_id").reindex(SLOTS).google_traffic_index
for i, v in enumerate(gi):
    ax.text(i, 103, f"Google +{(v - 1) * 100:.0f}%", ha="center", fontsize=6.5)
ax.set_xticks(range(4)); ax.set_xticklabels(SLAB); ax.set_ylim(0, 112); ax.set_ylabel("Share of answers (%)")
ax.legend(fontsize=6.5, loc="center left", bbox_to_anchor=(1.0, 0.5), handlelength=1)
fig.tight_layout(pad=0.3); save(fig, "fig_traffic_levels.pdf")

# 7. Where Gemini does worst: typical miss (median % error) by length, and road type on routes >= 5 km
fig, ax = plt.subplots(1, 2, figsize=(3.5, 1.7), sharey=True, gridspec_kw={"width_ratios": [3, 2]})
x = np.arange(3); w = 0.36
tm = [rm[rm.band == b].med_ape_time.median() * 100 for b in BANDS]
dm = [rm[rm.band == b].med_ape_dist.median() * 100 for b in BANDS]
ax[0].bar(x - w / 2, tm, w, color=M, label="Time"); ax[0].bar(x + w / 2, dm, w, color="#f3b393", label="Distance")
for i in range(3):
    ax[0].text(i - w / 2, tm[i] + 1, f"{tm[i]:.0f}", ha="center", fontsize=6.5)
    ax[0].text(i + w / 2, dm[i] + 1, f"{dm[i]:.0f}", ha="center", fontsize=6.5)
ax[0].set_xticks(x); ax[0].set_xticklabels(BLAB); ax[0].set_title("(a) By route length", fontsize=8)
big = rm[rm.band != BANDS[0]]
x2 = np.arange(2)
for k, (rt, lab) in enumerate((("arterial", "Main"), ("sub_arterial", "Smaller"))):
    s = big[big.road_type == rt]
    tv, dv = s.med_ape_time.median() * 100, s.med_ape_dist.median() * 100
    ax[1].bar(k - w / 2, tv, w, color=M); ax[1].bar(k + w / 2, dv, w, color="#f3b393")
    ax[1].text(k - w / 2, tv + 1, f"{tv:.0f}", ha="center", fontsize=6.5)
    ax[1].text(k + w / 2, dv + 1, f"{dv:.0f}", ha="center", fontsize=6.5)
    print(" ", lab, len(s), round(tv, 1), round(dv, 1))
ax[1].set_xticks(x2); ax[1].set_xticklabels(["Main roads", "Smaller roads"]); ax[1].set_title("(b) Routes of 5 km+", fontsize=8)
ax[0].set_ylabel("Typical miss (%)"); ax[0].legend(fontsize=7, loc="upper right"); grid(ax[0]); grid(ax[1])
fig.tight_layout(pad=0.3, w_pad=0.6); save(fig, "fig_where_worst.pdf")
print("  bands time", [round(v, 1) for v in tm], "dist", [round(v, 1) for v in dm])

# 8. Prompt wording: weekday typical time on the 10 repeat routes, three prompt versions and Google
pe = pd.read_csv(f"{RES}/summary_prompt_effect.csv"); pe = pe[pe.subset == "10 repeat routes"].set_index("version")
cr = pd.read_csv(f"{R}/data/benchmark_v2/consistency_routes.csv").route_id
gw = d[(d.route_id.isin(cr)) & (d.day_type == "weekday")].groupby("slot_id").g_min.median().reindex(SLOTS)
fig, ax = plt.subplots(figsize=(3.5, 1.65))
for v, lab, c, mk in (("round1", "Gemini, earlier prompt", "#8e44ad", "^"), ("control", "Gemini, neutral, whole route", GREEN, "s"),
                      ("round2", "Gemini, neutral, road by road", M, "o")):
    ax.plot(range(4), [pe.loc[v, f"weekday_min_{s}"] for s in SLOTS], color=c, marker=mk, ms=2.8, lw=1.0, label=lab)
ax.plot(range(4), gw.values, color=G, marker="D", ms=2.6, lw=1.0, ls="--", label="Google")
ax.set_xticks(range(4)); ax.set_xticklabels(SLAB); ax.set_ylabel("Typical weekday time (min)"); grid(ax)
ax.legend(fontsize=6.5, loc="center left", bbox_to_anchor=(1.0, 0.5), handlelength=1.5)
fig.tight_layout(pad=0.3); save(fig, "fig_prompt_effect.pdf")
print("  google 10 routes weekday", gw.round(1).tolist())
