"""Variation of the cleaned road legs: (a) distribution, (b) daily swing against left-over variation.

Usage: python volatility_figure.py <dir with legs.csv from traffic_reanalysis.py> <output dir>
"""
import sys
import numpy as np, pandas as pd
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt

SP, OUT = sys.argv[1], sys.argv[2]
plt.rcParams.update({"font.family": "serif", "font.serif": ["Times New Roman", "Nimbus Roman", "DejaVu Serif"],
                     "font.size": 8, "axes.spines.top": False, "axes.spines.right": False, "axes.edgecolor": "#555",
                     "axes.linewidth": 0.6, "xtick.major.width": 0.6, "ytick.major.width": 0.6})
L = pd.read_csv(f"{SP}/legs.csv")
cut = L.cv.quantile(0.8)

fig, ax = plt.subplots(1, 2, figsize=(3.5, 1.7))
bins = np.arange(0, 0.62, 0.02)
v = L.cv.clip(upper=0.6)
ax[0].hist(v[v < cut], bins=bins, color="#b5b5b5", edgecolor="white", lw=0.3)
ax[0].hist(v[v >= cut], bins=bins, color="#c0392b", edgecolor="white", lw=0.3)
ax[0].set_xlabel("Variation (CV)"); ax[0].set_ylabel("Legs")
ax[0].set_title("(a) Variation of 564 legs", fontsize=8)

s = L.dropna(subset=["swing", "resid"])
rho = s.swing.rank().corr(s.resid.rank())
ax[1].scatter(s.swing.clip(upper=3.5), s.resid.clip(upper=0.25), s=2.5, color="#555", alpha=0.55, lw=0)
ax[1].set_xlabel("Daily swing (max / min)"); ax[1].set_ylabel("Left-over variation")
ax[1].set_title("(b) Daily swing vs left-over", fontsize=8)
ax[1].text(0.97, 0.95, f"$\\rho$ = {rho:.2f}", transform=ax[1].transAxes, ha="right", va="top", fontsize=7)
for a in ax:
    a.grid(axis="y", color="#e4e3df", lw=0.5); a.set_axisbelow(True)
fig.tight_layout(pad=0.3, w_pad=0.8)
fig.savefig(f"{OUT}/fig_leg_variation.pdf"); plt.close(fig)
print("legs", len(L), "cut", round(cut, 3), "zero-variation legs", int((L.cv == 0).sum()), "rho", round(rho, 3))
