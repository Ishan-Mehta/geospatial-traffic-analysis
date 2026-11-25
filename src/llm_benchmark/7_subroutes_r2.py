"""
Step 7 (Round 2): sub-route comparison — an LLM's road-by-road answers vs Google's sub-routes. Offline, NO API calls.

Google sub-routes (4_query_gmaps_v2.py --part subroutes): one group per named road from the turn-by-turn steps
(exact distance, no-traffic time) and one leg per group from the stopover request (traffic-aware time; the stop sits
40 m, or 150 m after a retry, past the road change, so leg distances are shifted by that much).
LLM: `suggested_route` = [{road_name, distance_km, time_minutes}, ...].

An LLM road is paired with a Google sub-route when the names match (fuzzy score >= MATCH_MIN after normalisation,
the same rule as the Phase-4 road comparison). Google often uses highway numbers ("NH 44") where other sources use
street names ("Outer Ring Road"), so pairing is partial; coverage is reported.

Usage: BENCHMARK_ROUND=2 python 7_subroutes_r2.py [--model KEY]
Outputs (results/<model>/): subroute_pairs_<model>.csv, summary_subroutes.csv
"""

import argparse
import importlib
import math

import numpy as np
import pandas as pd

import config as C
from v2_common import read_jsonl

cmp_ = importlib.import_module("5_compare_results_v2")


def main():
    if C.V2_ROUND != "2":
        raise SystemExit("Round 2 only (set BENCHMARK_ROUND=2).")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", default=C.V2_ACTIVE_LLM)
    model = ap.parse_args().model
    res_dir = C.results_dir(model)
    res_dir.mkdir(parents=True, exist_ok=True)
    google = {(r["route_id"], r["day"], r["slot_id"]): r
              for r in read_jsonl(C.V2_GMAPS_DIR / C.V2_GMAPS_SUBROUTE_RESPONSES_JSONL) if r.get("status") == "ok"}
    llm = {(r["route_id"], r["day"], r["slot_id"]): r["parsed_response"]
           for r in read_jsonl(C.V2_LLM_DIR / f"{model}_A.jsonl") if r.get("status") == "ok" and r["sample_idx"] == 0}

    pairs, per_query = [], []
    for key, g in google.items():
        p = llm.get(key)
        if p is None:
            continue
        legs = g["routes"][0]["legs"]
        groups = g["groups"]
        g_names = [cmp_.norm_road(x["road"] or "") for x in groups]
        used, covered_m = set(), 0
        for x in p["suggested_route"]:
            n = cmp_.norm_road(x["road_name"])
            scores = [(cmp_.road_score(n, gn), i) for i, gn in enumerate(g_names) if gn and i not in used]
            best = max(scores, default=(0, None))
            if best[0] >= cmp_.MATCH_MIN:
                i = best[1]
                used.add(i)
                covered_m += groups[i]["distance_m"]
                lg = legs[i] if i < len(legs) else None
                pairs.append({"route_id": key[0], "day": key[1], "slot_id": key[2], "llm_road": x["road_name"],
                              "google_road": groups[i]["road"], "score": round(best[0], 1),
                              "llm_km": x["distance_km"], "llm_min": x["time_minutes"],
                              "google_km": groups[i]["distance_m"] / 1000,
                              "google_leg_min": lg["duration_s"] / 60 if lg else np.nan,
                              "google_static_min": groups[i]["static_duration_s"] / 60})
        whole = g["whole_route"]["distance_m"]
        per_query.append({"route_id": key[0], "slot_id": key[2], "n_google": len(groups), "n_llm": len(p["suggested_route"]),
                          "n_paired": len(used), "covered_share": covered_m / whole if whole else np.nan})

    pq, pr = pd.DataFrame(per_query), pd.DataFrame(pairs)
    pr.to_csv(res_dir / f"subroute_pairs_{model}.csv", index=False)
    lr = lambda a, b: np.log(np.asarray(a, float) / np.asarray(b, float))
    ok = pr[(pr.llm_km > 0) & (pr.google_km > 0.1) & (pr.llm_min > 0) & (pr.google_leg_min > 0)]
    dist_lr, time_lr = lr(ok.llm_km, ok.google_km), lr(ok.llm_min, ok.google_leg_min)
    summary = {
        "queries": len(pq),
        "google_subroutes_per_query_median": pq.n_google.median(),
        "llm_roads_per_query_median": pq.n_llm.median(),
        "queries_with_any_pair_share": round(float((pq.n_paired > 0).mean()), 3),
        "paired_roads_per_query_mean": round(float(pq.n_paired.mean()), 2),
        "google_distance_covered_by_pairs_median": round(float(pq.covered_share.median()), 3),
        "pairs": len(ok),
        "pair_distance_ratio_median": round(math.exp(np.median(dist_lr)), 3),
        "pair_distance_abs_pct_error_median": round(float(np.median(np.abs(np.exp(dist_lr) - 1))), 3),
        "pair_time_ratio_median": round(math.exp(np.median(time_lr)), 3),
        "pair_time_abs_pct_error_median": round(float(np.median(np.abs(np.exp(time_lr) - 1))), 3),
    }
    for s in ("AM_PEAK", "MID_DAY", "PM_PEAK", "NIGHT"):
        m = (ok.slot_id == s).values
        summary[f"pair_time_ratio_median_{s}"] = round(math.exp(np.median(time_lr[m])), 3)
    pd.Series(summary).to_csv(res_dir / "summary_subroutes.csv", header=["value"])
    print(pd.Series(summary).to_string())
    top = pr.google_road.value_counts().head(8)
    print("\nMost often paired Google roads:\n" + top.to_string())


if __name__ == "__main__":
    main()
