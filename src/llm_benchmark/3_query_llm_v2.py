"""
Step 3 (v2): LLM queries — provider-agnostic (model chosen in config.V2_LLM_MODELS).

Subcommands (run from src/llm_benchmark/):
  select-consistency                 offline: pick the 10 routes that get 2 extra samples (condition A)
  grounding       [--dry-run|--limit N|--mock]   "Where is <landmark>?" once per landmark used in routes
  grounding-eval  [--mock]           offline: LLM coordinate vs Google coordinate, flag > 2 km
  benchmark --condition A|B [--part main|consistency|all] [--dry-run|--limit N|--mock]
                                     the benchmark prompt for every query (route × day × slot)
  status          [--mock]           progress of every output file, no network
Common: --model <key in V2_LLM_MODELS> (default V2_ACTIVE_LLM). --mock forces the offline mock
model and writes to data/benchmark_v2/mock/llm/.

The benchmark prompt wording and JSON schema are IDENTICAL to v1 (D-13); only the origin /
destination strings (landmark names) and the weekday change. Condition A = lowest thinking
setting, B = high thinking (D-26); B runs last and only after approval (D-09).

Safety: every answer is appended to JSONL immediately; reruns skip items already OK; failures
are stored with the error and retried next run; fatal configuration errors stop the run.
"""

import argparse
import datetime as dt
import sys
import time
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

import config as C
from llm_clients import call_llm
from v2_common import append_jsonl, haversine_m, read_jsonl, sha1_short, stable_hash

IST = ZoneInfo("Asia/Kolkata")

# Identical to v1 src/llm_benchmark/3_query_llm.py ROUTE_SCHEMA (D-13) — do not edit.
ROUTE_SCHEMA = {
    'type': 'OBJECT',
    'required': ['suggested_route', 'estimated_distance_km', 'estimated_time_minutes', 'traffic_awareness', 'reasoning'],
    'properties': {
        'suggested_route': {'type': 'ARRAY', 'items': {'type': 'STRING'}},
        'estimated_distance_km': {'type': 'NUMBER'},
        'estimated_time_minutes': {'type': 'NUMBER'},
        'traffic_awareness': {'type': 'STRING', 'enum': ['none', 'light', 'moderate', 'heavy']},
        'reasoning': {'type': 'STRING'},
    },
}

GROUNDING_SCHEMA = {
    'type': 'OBJECT',
    'required': ['locality', 'latitude', 'longitude', 'confidence'],
    'properties': {
        'locality': {'type': 'STRING'},
        'latitude': {'type': 'NUMBER'},
        'longitude': {'type': 'NUMBER'},
        'confidence': {'type': 'STRING', 'enum': ['low', 'medium', 'high']},
    },
}


def benchmark_prompt(origin: str, destination: str, day: str, slot_label: str) -> str:
    """v1 wording (3_query_llm.py), unchanged."""
    return (
        f"Origin: {origin}\n"
        f"Destination: {destination}\n"
        f"City: Bangalore, India\n"
        f"Day of the week: {day}\n"
        f"Time of day: {slot_label}"
    )


def grounding_prompt(name: str) -> str:
    return (f"Place: {name}\nCity: Bangalore, India\n"
            f"Where exactly is this place? Give its locality/area and your best estimate of its latitude and longitude.")


def llm_dir(mock: bool):
    return (C.V2_MOCK_DIR / "llm") if mock else C.V2_LLM_DIR


# =====================================================================
#  Consistency subset (offline, deterministic)
# =====================================================================
def cmd_select_consistency(args):
    """One route per group (fixed hash order), then greedily add the group that keeps band,
    road type and hotspot exposure as balanced as possible (minimum sum of squared counts)."""
    od = pd.read_csv(C.V2_OD_PAIRS_CSV)
    od["h"] = [stable_hash("consistency", r) for r in od.route_id]
    reps = od.sort_values("h").groupby("group").head(1).sort_values("h")
    picked, counts = [], {}
    for _ in range(C.V2_CONSISTENCY_N_ROUTES):
        def cost(row):
            return sum((counts.get((f, row[f]), 0) + 1) ** 2 for f in ("band", "road_type", "hotspot_exposure"))
        remaining = reps[~reps.route_id.isin([p.route_id for p in picked])]
        best = min(remaining.itertuples(index=False), key=lambda r: (cost(r._asdict()), r.h))
        picked.append(best)
        for f in ("band", "road_type", "hotspot_exposure"):
            counts[(f, getattr(best, f))] = counts.get((f, getattr(best, f)), 0) + 1
    picked = [pd.Series(p._asdict()) for p in picked]
    sel = pd.DataFrame(picked).drop(columns="h")[["route_id", "origin_name", "dest_name", "band", "road_type",
                                                   "hotspot_exposure", "group"]]
    sel.to_csv(C.V2_CONSISTENCY_ROUTES_CSV, index=False)
    print(sel.to_string(index=False))
    print(f"\nCoverage — bands: {sel.band.value_counts().to_dict()} | road types: {sel.road_type.value_counts().to_dict()}"
          f" | exposure: {sel.hotspot_exposure.value_counts().to_dict()}")
    print(f"Saved {C.V2_CONSISTENCY_ROUTES_CSV}")


# =====================================================================
#  Work items
# =====================================================================
def benchmark_items(part: str, condition: str) -> list:
    od = pd.read_csv(C.V2_OD_PAIRS_CSV)
    samples = {0: od.route_id.tolist()}
    if part in ("consistency", "all"):
        if condition != "A":
            sys.exit("The consistency subset is defined for condition A only (D-09).")
        if not C.V2_CONSISTENCY_ROUTES_CSV.exists():
            sys.exit("consistency_routes.csv missing — run `select-consistency` first.")
        cons = pd.read_csv(C.V2_CONSISTENCY_ROUTES_CSV).route_id.tolist()
        for k in range(1, C.V2_CONSISTENCY_EXTRA_SAMPLES + 1):
            samples[k] = cons
        if part == "consistency":
            del samples[0]
    odi = od.set_index("route_id")
    items = []
    for k, rids in samples.items():
        for rid in rids:
            r = odi.loc[rid]
            for day in C.V2_DAYS:
                for slot in C.TIME_SLOTS:
                    items.append({"key": (rid, day, slot["id"], k), "route_id": rid, "day": day,
                                  "slot_id": slot["id"], "slot_label": slot["label"], "sample_idx": k,
                                  "origin_id": r.origin_id, "dest_id": r.dest_id,
                                  "origin_name": r.origin_name, "dest_name": r.dest_name,
                                  "prompt": benchmark_prompt(r.origin_name, r.dest_name, day, slot["label"])})
    # Reproducible shuffled order (D-35): any drift during the run spreads over all routes/groups.
    items.sort(key=lambda it: stable_hash(C.V2_SHUFFLE_SEED, *it["key"]))
    return items


def grounding_items() -> list:
    od = pd.read_csv(C.V2_OD_PAIRS_CSV)
    ids = sorted(set(od.origin_id) | set(od.dest_id))
    names = {**dict(zip(od.origin_id, od.origin_name)), **dict(zip(od.dest_id, od.dest_name))}
    return [{"key": (lid,), "landmark_id": lid, "llm_name": names[lid], "prompt": grounding_prompt(names[lid])}
            for lid in ids]


def record_key(rec: dict, kind: str):
    if kind == "grounding":
        return (rec["landmark_id"],)
    return (rec["route_id"], rec["day"], rec["slot_id"], rec["sample_idx"])


# =====================================================================
#  Runner (shared by grounding and benchmark)
# =====================================================================
def run(kind: str, items: list, model_key: str, condition: str, system_prompt: str, schema: dict,
        out_path, dry_run: bool, limit: int, mock: bool):
    cfg = C.V2_LLM_MODELS[model_key]
    records = read_jsonl(out_path)
    done = {record_key(r, kind) for r in records if r.get("status") == "ok"}
    pending = [it for it in items if it["key"] not in done]
    todo = pending[:limit] if limit else pending
    n_err = sum(1 for r in records if r.get("status") != "ok")

    tin, tout = cfg["est_tokens"][condition]
    cost = len(todo) * (tin * cfg["price_in_per_m"] + tout * cfg["price_out_per_m"]) / 1e6
    print(f"Model: {model_key} ({cfg['provider']} / {cfg['model_name']}) · condition {condition} "
          f"· settings {cfg['conditions'][condition]} · temperature {cfg['temperature']}")
    print(f"Output: {out_path}{'  [MOCK]' if mock else ''}")
    print(f"Items: {len(items)} | done OK: {len(done)} | pending: {len(pending)} | error records so far: {n_err}")
    print(f"This run: {len(todo)} calls · estimated cost ≈ ${cost:.2f} "
          f"(assumes ~{tin} input + ~{tout} output/thinking tokens per call)")
    if dry_run:
        if todo:
            print("\nSystem prompt:\n" + system_prompt + "\n\nSample user prompt:\n" + todo[0]["prompt"])
        print("\nDRY RUN — no network calls made.")
        return

    sys_sha = sha1_short(system_prompt)
    made = 0
    for i, it in enumerate(todo, 1):
        res, attempts, bad = None, 0, 0
        while attempts < C.V2_LLM_MAX_ATTEMPTS:
            attempts += 1
            res = call_llm(model_key, system_prompt, it["prompt"], schema, condition)
            made += 1
            if res.ok or res.error_kind == "fatal":
                break
            if res.error_kind == "bad_output":
                bad += 1
                if bad >= 3:
                    break
                continue
            wait = res.retry_after_s or min(60, 2 ** attempts)
            wait = 0 if mock else wait
            print(f"    retry {attempts}/{C.V2_LLM_MAX_ATTEMPTS} in {wait:.0f}s ({res.error[:70]})")
            time.sleep(wait)
        rec = {k: v for k, v in it.items() if k not in ("key",)}
        rec.update({"kind": kind, "condition": condition, "model_key": model_key, "provider": cfg["provider"],
                    "model_name": cfg["model_name"], "system_prompt_sha1": sys_sha,
                    "status": "ok" if res.ok else "error", "attempts": attempts,
                    "parsed_response": res.parsed, "raw_response": res.raw_text,
                    "model_version": res.model_version, "settings": res.settings,
                    "prompt_tokens": res.prompt_tokens, "output_tokens": res.output_tokens,
                    "thought_tokens": res.thought_tokens, "latency_s": res.latency_s,
                    "error": res.error, "error_kind": res.error_kind, "mock": mock,
                    "query_timestamp": dt.datetime.now(IST).isoformat(timespec="seconds")})
        if kind == "benchmark" and res.ok:
            p = res.parsed or {}
            rec["valid_numbers"] = bool(isinstance(p.get("estimated_distance_km"), (int, float))
                                        and isinstance(p.get("estimated_time_minutes"), (int, float))
                                        and p["estimated_distance_km"] > 0 and p["estimated_time_minutes"] > 0)
        append_jsonl(out_path, rec)
        label = it.get("route_id", it.get("landmark_id"))
        extra = (f"{it['day'][:3]} {it['slot_id']:8s} s{it['sample_idx']}" if kind == "benchmark" else it["llm_name"])
        if res.ok:
            p = res.parsed
            summ = (f"{p.get('estimated_distance_km')} km, {p.get('estimated_time_minutes')} min, {p.get('traffic_awareness')}"
                    if kind == "benchmark" else f"{p.get('locality')} ({p.get('latitude')}, {p.get('longitude')})")
            print(f"[{i}/{len(todo)}] OK  {label} {extra} -> {summ} · thought tokens {res.thought_tokens}")
        else:
            print(f"[{i}/{len(todo)}] ERR {label} {extra} -> {res.error}")
        if res.error_kind == "fatal":
            print(f"STOPPED: {res.error}")
            break
        if not mock:
            time.sleep(cfg.get("min_interval_s", 0))
    print(f"API calls made this run (incl. retries): {made}{' (mock, no network)' if mock else ''}")


# =====================================================================
#  Grounding evaluation (offline)
# =====================================================================
def cmd_grounding_eval(args, model_key):
    d = llm_dir(args.mock)
    recs = [r for r in read_jsonl(d / f"{model_key}_grounding.jsonl") if r.get("status") == "ok"]
    if not recs:
        sys.exit("No grounding answers yet — run `grounding` first.")
    lm = pd.read_csv(C.V2_LANDMARKS_GEOCODED_CSV).set_index("landmark_id")
    rows = []
    for r in {x["landmark_id"]: x for x in recs}.values():
        p = r["parsed_response"]
        g = lm.loc[r["landmark_id"]]
        dist = float(haversine_m(g.lat, g.lng, p["latitude"], p["longitude"]))
        rows.append({"landmark_id": r["landmark_id"], "llm_name": r["llm_name"], "google_lat": g.lat,
                     "google_lng": g.lng, "llm_lat": p["latitude"], "llm_lng": p["longitude"],
                     "llm_locality": p["locality"], "llm_confidence": p["confidence"],
                     "error_m": round(dist), "misplaced": dist > C.V2_GROUNDING_MAX_M})
    res = pd.DataFrame(rows).sort_values("error_m", ascending=False)
    res.to_csv(d / f"{model_key}_grounding_results.csv", index=False)
    od = pd.read_csv(C.V2_OD_PAIRS_CSV)
    bad = set(res[res.misplaced].landmark_id)
    od["origin_misplaced"], od["dest_misplaced"] = od.origin_id.isin(bad), od.dest_id.isin(bad)
    od["grounding_flag"] = od.origin_misplaced | od.dest_misplaced
    od[["route_id", "origin_id", "dest_id", "origin_misplaced", "dest_misplaced", "grounding_flag"]].to_csv(
        d / f"{model_key}_grounding_route_flags.csv", index=False)
    print(f"Landmarks evaluated: {len(res)} | median error {res.error_m.median():.0f} m | "
          f"misplaced (> {C.V2_GROUNDING_MAX_M / 1000:.0f} km): {len(bad)}")
    print(f"Routes with a misplaced endpoint: {int(od.grounding_flag.sum())} of {len(od)}")
    print(res.head(10)[["landmark_id", "llm_name", "llm_locality", "error_m", "misplaced"]].to_string(index=False))


def cmd_status(args, model_key):
    d = llm_dir(args.mock)
    files = sorted(d.glob("*.jsonl")) if d.exists() else []
    if not files:
        print(f"No LLM output files in {d}")
    for f in files:
        recs = read_jsonl(f)
        ok = [r for r in recs if r.get("status") == "ok"]
        th = [r["thought_tokens"] for r in ok if r.get("thought_tokens") is not None]
        print(f"{f.name}: {len(ok)} OK, {len(recs) - len(ok)} error records"
              f"{f' · median thought tokens {np.median(th):.0f}' if th else ''}")


# =====================================================================
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", default=C.V2_ACTIVE_LLM)
    ap.add_argument("--mock", action="store_true")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("select-consistency")
    for name in ("grounding", "benchmark"):
        p = sub.add_parser(name)
        p.add_argument("--dry-run", action="store_true")
        p.add_argument("--limit", type=int)
        if name == "benchmark":
            p.add_argument("--condition", choices=["A", "B"], required=True)
            p.add_argument("--part", choices=["main", "consistency", "all"], default="main")
    sub.add_parser("grounding-eval")
    sub.add_parser("status")
    args = ap.parse_args()
    model_key = "mock" if args.mock else args.model
    if model_key not in C.V2_LLM_MODELS:
        sys.exit(f"Unknown model '{model_key}'. Options: {list(C.V2_LLM_MODELS)}")

    if args.cmd == "select-consistency":
        return cmd_select_consistency(args)
    if args.cmd == "grounding-eval":
        return cmd_grounding_eval(args, model_key)
    if args.cmd == "status":
        return cmd_status(args, model_key)

    d = llm_dir(args.mock)
    if args.cmd == "grounding":
        system_prompt = C.V2_GROUNDING_SYSTEM_PROMPT_FILE.read_text(encoding="utf-8").strip()
        run("grounding", grounding_items(), model_key, "A", system_prompt, GROUNDING_SCHEMA,
            d / f"{model_key}_grounding.jsonl", args.dry_run, args.limit, args.mock)
    else:
        if args.condition == "B" and not args.dry_run and not args.mock:
            print("NOTE: condition B (thinking on) is the costliest step and needs Ishan's explicit approval (D-09).")
        system_prompt = C.SYSTEM_PROMPT_FILE.read_text(encoding="utf-8").strip()
        run("benchmark", benchmark_items(args.part, args.condition), model_key, args.condition, system_prompt,
            ROUTE_SCHEMA, d / f"{model_key}_{args.condition}.jsonl", args.dry_run, args.limit, args.mock)


if __name__ == "__main__":
    main()
