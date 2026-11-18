"""
Step 8: effect of the prompt wording — Round 1 (original prompt) vs Round 2 (neutral prompt). Offline, NO API calls.

Same model, same questions (route × day × time; the questions contain no date), three versions:
  round1   original prompt ("Morning Rush (08:00)", "Bangalore has heavy peak-hour traffic"), whole-route answer
  control  neutral prompt, whole-route answer (Round 2 format control: the 10 repeat routes only)
  round2   neutral prompt, road-by-road answer (Round 2 main run)
The control separates the effect of the wording (round1 vs control) from the effect of the answer format
(control vs round2). A model without Round 1 data (e.g. ChatGPT) gets only control vs round2.

Usage: python 8_prompt_effect.py [--model KEY]   (run from src/llm_benchmark/, any BENCHMARK_ROUND)
Outputs: data/benchmark_round2/results/<model>/summary_prompt_effect.csv,
         docs/benchmark/round2/figures/<model>/fig_I_prompt_effect.png
"""

import argparse
import math
import statistics as st

import pandas as pd

import config as C
from v2_common import read_jsonl

SLOTS = ["AM_PEAK", "MID_DAY", "PM_PEAK", "NIGHT"]
SLOT_LABELS = {"AM_PEAK": "8 am", "MID_DAY": "2 pm", "PM_PEAK": "6 pm", "NIGHT": "11 pm"}
WEEKEND = {"Saturday", "Sunday"}
VERSIONS = {"round1": "Original prompt", "control": "Neutral, whole route", "round2": "Neutral, road by road"}
COLOURS = {"round1": "#eb6834", "control": "#1baf7a", "round2": "#2a78d6"}       # palette slots 2, 3, 1
ROUND2_DIR = C._PROJECT_ROOT / "data" / "benchmark_round2"


def load(path) -> dict:
    """{(route, day, slot): answer} for the first answer of every query."""
    return {(r["route_id"], r["day"], r["slot_id"]): r["parsed_response"] for r in read_jsonl(path)
            if r.get("status") == "ok" and r.get("sample_idx", 0) == 0}


def weekday(d: dict, routes: set, slot: str) -> list:
    return [v for k, v in d.items() if k[0] in routes and k[2] == slot and k[1] not in WEEKEND]


def peak_night(d: dict, routes: set) -> float:
    """Median over routes of (mean weekday 08:00 + 18:00 time) ÷ (mean weekday 23:00 time)."""
    out = []
    for rt in routes:
        pk = [v["estimated_time_minutes"] for k, v in d.items()
              if k[0] == rt and k[1] not in WEEKEND and k[2] in ("AM_PEAK", "PM_PEAK")]
        nt = [v["estimated_time_minutes"] for k, v in d.items() if k[0] == rt and k[1] not in WEEKEND and k[2] == "NIGHT"]
        if pk and nt:
            out.append(st.mean(pk) / st.mean(nt))
    return round(st.median(out), 3)


def summarise(name: str, d: dict, routes: set, ref: dict = None) -> dict:
    row = {"version": name, "routes": len(routes), "queries": sum(1 for k in d if k[0] in routes),
           "peak_night_ratio": peak_night(d, routes),
           "distance_km_median": st.median(v["estimated_distance_km"] for k, v in d.items() if k[0] in routes)}
    for s in SLOTS:
        w = weekday(d, routes, s)
        row[f"weekday_min_{s}"] = st.median(v["estimated_time_minutes"] for v in w)
        row[f"weekday_heavy_{s}"] = round(sum(v["traffic_awareness"] == "heavy" for v in w) / len(w), 3)
    if ref:
        lr = [math.log(v["estimated_time_minutes"] / ref[k]["estimated_time_minutes"]) for k, v in d.items()
              if k[0] in routes and k in ref]
        row["time_vs_round1_median"] = round(math.exp(st.median(lr)), 3)
    return row


def plot(rows: list, out):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    fig, axes = plt.subplots(1, 2, figsize=(9, 3.6))
    x = np.arange(len(SLOTS))
    w = 0.8 / len(rows)
    for i, r in enumerate(rows):
        night = r["weekday_min_NIGHT"]
        rel = [r[f"weekday_min_{s}"] / night for s in SLOTS]
        axes[0].plot(x, rel, marker="o", lw=2, color=COLOURS[r["version"]], label=VERSIONS[r["version"]])
        bars = axes[1].bar(x - 0.4 + w * (i + 0.5), [r[f"weekday_heavy_{s}"] for s in SLOTS], w * 0.95,
                           color=COLOURS[r["version"]], label=VERSIONS[r["version"]])
        axes[1].bar_label(bars, labels=[f"{b.get_height():.0%}" if b.get_height() else "" for b in bars], fontsize=6)
    for ax, title in ((axes[0], "Weekday time ÷ same trip at 11 pm"), (axes[1], "Weekday answers labelled “heavy”")):
        ax.set_xticks(x, [SLOT_LABELS[s] for s in SLOTS])
        ax.set_title(title, fontsize=10, loc="left")
        ax.spines[["top", "right"]].set_visible(False)
    axes[1].set_yticks([0, 0.5, 1], ["0%", "50%", "100%"])
    axes[1].set_ylim(0, 1.12)
    axes[0].legend(frameon=False, fontsize=8)
    fig.tight_layout()
    out.mkdir(parents=True, exist_ok=True)
    fig.savefig(out / "fig_I_prompt_effect.png", dpi=200, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", default=C.V2_ACTIVE_LLM)
    model = ap.parse_args().model
    r1 = load(C.V2_DIR / "llm" / f"{model}_A.jsonl")
    r2 = load(ROUND2_DIR / "llm" / f"{model}_A.jsonl")
    ctl = load(ROUND2_DIR / "llm" / f"{model}_A_format_control.jsonl")
    if not r2:
        raise SystemExit(f"No Round 2 answers for {model}.")
    all_routes = {k[0] for k in r2}
    rows = []
    if r1:
        rows.append({"subset": "all routes", **summarise("round1", r1, all_routes)})
        rows.append({"subset": "all routes", **summarise("round2", r2, all_routes, r1)})
    if ctl:
        cons = {k[0] for k in ctl}
        sub = [("round1", r1)] if r1 else []
        for name, d in sub + [("control", ctl), ("round2", r2)]:
            rows.append({"subset": "10 repeat routes", **summarise(name, d, cons, r1 or None)})
    table = pd.DataFrame(rows)
    res = ROUND2_DIR / "results" / model
    res.mkdir(parents=True, exist_ok=True)
    table.to_csv(res / "summary_prompt_effect.csv", index=False)
    print(table.T.to_string(header=False))
    plot([r for r in rows if r["subset"] == "10 repeat routes"] or rows, C._PROJECT_ROOT / "docs" / "benchmark" /
         "round2" / "figures" / model)
    print(f"Saved {res / 'summary_prompt_effect.csv'} and fig_I_prompt_effect.png")


if __name__ == "__main__":
    main()
