"""
Step 9 (Round 2): Google Maps vs every LLM side by side. Offline, NO API calls.

Reads the per-model outputs of 5_compare_results_v2.py (and 7_subroutes_r2.py if present) from
data/benchmark_round2/results/<model>/ for every model that has them, and writes one table and two figures.
Run 5_compare_results_v2.py (and 7_subroutes_r2.py) for each model first.

Usage: BENCHMARK_ROUND=2 python 9_compare_models.py [--models gemini_38_flash,openai_main]
Outputs: data/benchmark_round2/results/summary_models.csv,
         docs/benchmark/round2/figures/fig_M1_time_by_slot_models.png, fig_M2_day_shape_models.png
"""

import argparse

import numpy as np
import pandas as pd

import config as C

SLOTS = ["AM_PEAK", "MID_DAY", "PM_PEAK", "NIGHT"]
SLOT_LABELS = {"AM_PEAK": "8 am", "MID_DAY": "2 pm", "PM_PEAK": "6 pm", "NIGHT": "11 pm"}
GOOGLE = "#2a78d6"
MODEL_COLOURS = ["#eb6834", "#1baf7a", "#eda100"]                      # palette slots 2-4, in fixed order


NAMES = {"gemini": "Gemini", "openai": "ChatGPT"}


def label(model: str) -> str:
    """Readable model name for tables and legends, e.g. "Gemini (gemini-3.8-flash)"."""
    cfg = C.V2_LLM_MODELS.get(model, {})
    name = NAMES.get(cfg.get("provider"), model)
    return f"{name} ({cfg['model_name']})" if cfg.get("model_name") else name


def model_row(model: str) -> dict:
    d = C.results_dir(model)
    c = pd.read_csv(next(d.glob("comparison_*_A.csv")))
    c = c[c.sample_idx == 0]
    ov = pd.read_csv(d / "summary_overall.csv", index_col=0)["value"]
    rd, rt = c.llm_km / c.g_km, c.llm_min / c.g_min
    wk = c[~c.is_weekend]
    row = {"model": label(model), "queries": len(c),
           "distance_ratio": rd.median(), "distance_typical_miss": (rd - 1).abs().median(),
           "time_ratio": rt.median(), "time_typical_miss": (rt - 1).abs().median(),
           "time_within_10pct": ((rt - 1).abs() <= 0.10).mean()}
    for s in SLOTS:
        row[f"weekday_time_ratio_{s}"] = (wk[wk.slot_id == s].llm_min / wk[wk.slot_id == s].g_min).median()
    for k in ("time_of_day_pn_llm_median", "time_of_day_pn_google_median", "within_route_time_rho_median",
              "label_spearman_all"):
        row[k] = float(ov[k])
    row["road_jaccard"] = c.jaccard_roads.mean()
    row["share_of_google_roads_named"] = c.recall_roads.mean()
    row["road_names_valid"] = c.validity_share.mean()
    cons = d / "summary_consistency.csv"
    if cons.exists():
        cv = pd.read_csv(cons, index_col=0)["value"]
        row["repeat_time_cv"] = float(cv["cv_time_median"])
    sub = d / "summary_subroutes.csv"
    if sub.exists():
        sv = pd.read_csv(sub, index_col=0)["value"]
        row["subroute_time_typical_miss"] = float(sv["pair_time_abs_pct_error_median"])
        row["subroute_distance_typical_miss"] = float(sv["pair_distance_abs_pct_error_median"])
    return {k: (round(v, 3) if isinstance(v, (float, np.floating)) else v) for k, v in row.items()}


def day_shape(model: str) -> pd.DataFrame:
    """Weekday time ÷ the same route's weekday-night time, median over queries (Google and the model)."""
    c = pd.read_csv(next(C.results_dir(model).glob("comparison_*_A.csv")))
    c = c[(c.sample_idx == 0) & (~c.is_weekend)]
    out = {}
    for src, col in (("google", "g_min"), ("llm", "llm_min")):
        ref = c[c.slot_id == "NIGHT"].groupby("route_id")[col].mean()
        out[src] = (c[col] / c.route_id.map(ref)).groupby(c.slot_id).median().reindex(SLOTS)
    return pd.DataFrame(out)


def plots(models: list, rows: list, out):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    out.mkdir(parents=True, exist_ok=True)
    x = np.arange(len(SLOTS))
    fig, ax = plt.subplots(figsize=(6.6, 3.6))
    w = 0.8 / len(models)
    for i, (m, r) in enumerate(zip(models, rows)):
        bars = ax.bar(x - 0.4 + w * (i + 0.5), [r[f"weekday_time_ratio_{s}"] for s in SLOTS], w * 0.95,
                      color=MODEL_COLOURS[i], label=r["model"])
        ax.bar_label(bars, labels=[f"{b.get_height():.2f}" for b in bars], fontsize=8)
    ax.axhline(1, color=GOOGLE, lw=1.5, ls="--", label="Google Maps (= 1)")
    ax.set_xticks(x, [SLOT_LABELS[s] for s in SLOTS])
    ax.set_ylabel("LLM time ÷ Google time (weekdays)")
    ax.set_ylim(0, max(r[f"weekday_time_ratio_{s}"] for r in rows for s in SLOTS) * 1.35)
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(frameon=False, fontsize=8, loc="upper left", ncol=2)
    fig.savefig(out / "fig_M1_time_by_slot_models.png", dpi=200, bbox_inches="tight", facecolor="white")
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(6.6, 3.6))
    shapes = [day_shape(m) for m in models]
    ax.plot(x, shapes[0]["google"].values, "o-", color=GOOGLE, lw=2, label="Google Maps")
    for i, (r, sh) in enumerate(zip(rows, shapes)):
        ax.plot(x, sh["llm"].values, "s-", color=MODEL_COLOURS[i], lw=2, label=r["model"])
    ax.axhline(1, color="#888", lw=0.8, ls=":")
    ax.set_xticks(x, [SLOT_LABELS[s] for s in SLOTS])
    ax.set_ylabel("times longer than the same trip at 11 pm")
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(frameon=False, fontsize=8)
    fig.savefig(out / "fig_M2_day_shape_models.png", dpi=200, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def main():
    if C.V2_ROUND != "2":
        raise SystemExit("Round 2 only (set BENCHMARK_ROUND=2).")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--models", help="comma list; default = every model with Round 2 results")
    args = ap.parse_args()
    base = C.V2_OUT_DIR / "results"
    models = (args.models.split(",") if args.models else
              sorted(p.name for p in base.iterdir() if p.is_dir() and any(p.glob("comparison_*_A.csv"))))
    if not models:
        raise SystemExit("No model results yet — run 5_compare_results_v2.py first.")
    rows = [model_row(m) for m in models]
    table = pd.DataFrame(rows).set_index("model").T
    table.to_csv(base / "summary_models.csv")
    print(table.to_string())
    plots(models, rows, C._PROJECT_ROOT / "docs" / "benchmark" / "round2" / "figures")
    print(f"Saved {base / 'summary_models.csv'} and figures fig_M1/fig_M2")


if __name__ == "__main__":
    main()
