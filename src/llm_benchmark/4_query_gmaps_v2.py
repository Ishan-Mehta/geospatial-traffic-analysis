"""
Step 4 (v2): Google Maps ground truth for every query (route × day × time slot).

28 queries per route (Monday–Sunday × AM_PEAK 08:00 / MID_DAY 14:00 / PM_PEAK 18:00 / NIGHT 23:00 IST).
Departure times are in the FUTURE, all inside one fixed reference week, so Google returns its
*predicted typical traffic* for that week (D-08) — label results as "predicted", not "live".

Usage (from src/llm_benchmark/):
  python 4_query_gmaps_v2.py --dry-run        # count + cost + sample request, NO network
  python 4_query_gmaps_v2.py --limit 1        # PAID: exactly one query (test), after approval
  python 4_query_gmaps_v2.py                  # PAID: all pending queries, after approval
  python 4_query_gmaps_v2.py --mock           # offline fake answers -> data/benchmark_v2/mock/gmaps/
  python 4_query_gmaps_v2.py --status         # progress summary, NO network

Round 2 (run with BENCHMARK_ROUND=2 in the environment; outputs in data/benchmark_round2/):
  --part whole       (default) the normal request; also stores road-by-road distance and no-traffic time
  --part subroutes   a second request per query, with stopovers where the road changes on that query's whole-route
                     path. Google gives traffic-aware time only per leg, and a route without stopovers has one leg.

Safety
- Each result is appended to gmaps_responses.jsonl immediately; reruns skip queries already OK.
- Failed queries are stored with status="error" and the error text, and are retried on the next run.
- Configuration errors (billing / API disabled / key) stop the run at the first occurrence.
- The API key is read from .env and never printed or written to disk.
"""

import argparse
import datetime as dt
import hashlib
import json
import math
import sys
import time
from zoneinfo import ZoneInfo

import pandas as pd

import config as C
from v2_common import (append_jsonl, friendly_api_error, haversine_m, is_fatal_error, load_env_key, read_jsonl,
                       stable_hash, subroute_groups)

IST = ZoneInfo("Asia/Kolkata")
UTC = dt.timezone.utc


# =====================================================================
#  Query plan
# =====================================================================
def out_dir(mock: bool):
    return (C.V2_MOCK_DIR / "gmaps") if mock else C.V2_GMAPS_DIR


def file_md5(path) -> str:
    return hashlib.md5(path.read_bytes()).hexdigest()


def next_reference_monday(now_ist: dt.datetime) -> dt.date:
    """The Monday of next week (always >= 1 day ahead, so every slot of the week is in the future)."""
    days_ahead = (7 - now_ist.weekday()) % 7 or 7
    return (now_ist + dt.timedelta(days=days_ahead)).date()


def departure_ist(ref_monday: dt.date, day: str, slot_time: str) -> dt.datetime:
    h, m = map(int, slot_time.split(":"))
    offset = C.V2_DAYS.index(day)
    if C.V2_WEEKEND_BEFORE_MONDAY and day in C.V2_WEEKEND_DAYS:
        offset -= 7
    d = ref_monday + dt.timedelta(days=offset)
    return dt.datetime(d.year, d.month, d.day, h, m, tzinfo=IST)


def load_or_create_manifest(d, mock: bool, create: bool):
    """The manifest freezes the reference week and request settings for the whole run."""
    path = d / C.V2_GMAPS_MANIFEST
    od_md5 = file_md5(C.V2_OD_PAIRS_CSV)
    if path.exists():
        man = json.loads(path.read_text())
        if man["od_pairs_md5"] != od_md5:
            sys.exit(f"od_pairs.csv changed since this run started (manifest {man['od_pairs_md5'][:8]} vs "
                     f"now {od_md5[:8]}). Move {d} aside to start a new run.")
        return man
    now = dt.datetime.now(IST)
    man = {
        "created_at_ist": now.isoformat(timespec="seconds"),
        "round": C.V2_ROUND,
        "reference_monday": (C.V2_REFERENCE_MONDAY or next_reference_monday(now).isoformat()),
        "weekend_before_monday": C.V2_WEEKEND_BEFORE_MONDAY,
        "routing_preference": C.V2_ROUTING_PREFERENCE,
        "traffic_model": C.V2_TRAFFIC_MODEL if C.V2_ROUTING_PREFERENCE == "TRAFFIC_AWARE_OPTIMAL" else None,
        "compute_alternatives": C.V2_COMPUTE_ALTERNATIVES,
        "field_mask": C.V2_GMAPS_FIELD_MASK,
        "days": C.V2_DAYS, "slots": C.TIME_SLOTS,
        "od_pairs_md5": od_md5, "mock": mock,
        "traffic_semantics": "predicted typical traffic for a future departure time (not live)",
    }
    if create:
        d.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(man, indent=2))
    return man


def build_queries(routes: pd.DataFrame, man: dict) -> list:
    ref = dt.date.fromisoformat(man["reference_monday"])
    qs = []
    for r in routes.itertuples():
        for day in C.V2_DAYS:
            for slot in C.TIME_SLOTS:
                dep = departure_ist(ref, day, slot["time"])
                qs.append({"route_id": r.route_id, "day": day, "slot_id": slot["id"], "slot_time": slot["time"],
                           "departure_ist": dep.isoformat(),
                           "departure_utc": dep.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
                           "origin": (r.origin_lat, r.origin_lng), "dest": (r.dest_lat, r.dest_lng)})
    # Reproducible shuffled order (D-35): any drift during the run spreads over all routes/groups.
    qs.sort(key=lambda q: stable_hash(C.V2_SHUFFLE_SEED, q["route_id"], q["day"], q["slot_id"]))
    return qs


def request_body(q: dict) -> dict:
    body = {
        "origin": {"location": {"latLng": {"latitude": q["origin"][0], "longitude": q["origin"][1]}}},
        "destination": {"location": {"latLng": {"latitude": q["dest"][0], "longitude": q["dest"][1]}}},
        "travelMode": "DRIVE",
        "routingPreference": C.V2_ROUTING_PREFERENCE,
        "departureTime": q["departure_utc"],
        "computeAlternativeRoutes": C.V2_COMPUTE_ALTERNATIVES,
        "polylineEncoding": "GEO_JSON_LINESTRING",
        "languageCode": "en-US",
        "units": "METRIC",
    }
    if C.V2_ROUTING_PREFERENCE == "TRAFFIC_AWARE_OPTIMAL":
        body["trafficModel"] = C.V2_TRAFFIC_MODEL
    return body


def stop_point(polyline: list, point: list, offset_m: float):
    """The stop moved offset_m along the whole-route line past a road change, with the compass direction of travel
    there. Road changes are often junctions with flyovers or underpasses, where a stop can snap to the wrong level
    and add a detour. polyline = [[lng, lat], ...], point = [lat, lng]. Returns ([lat, lng], heading)."""
    if not polyline or point[0] is None:
        return point, None
    i = min(range(len(polyline)), key=lambda k: (polyline[k][1] - point[0]) ** 2 + (polyline[k][0] - point[1]) ** 2)
    walked = 0.0
    while i < len(polyline) - 2 and walked < offset_m:
        walked += haversine_m(polyline[i][1], polyline[i][0], polyline[i + 1][1], polyline[i + 1][0])
        i += 1
    (lng1, lat1), (lng2, lat2) = polyline[max(i - 1, 0)], polyline[min(i + 1, len(polyline) - 1)]
    y = math.sin(math.radians(lng2 - lng1)) * math.cos(math.radians(lat2))
    x = (math.cos(math.radians(lat1)) * math.sin(math.radians(lat2))
         - math.sin(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.cos(math.radians(lng2 - lng1)))
    return [polyline[i][1], polyline[i][0]], round(math.degrees(math.atan2(y, x))) % 360


def subroute_body(q: dict, groups: list) -> dict:
    """Same request as the whole route, with a stopover at the end of every sub-route but the last, approached in the
    whole route's direction of travel. Google does not return alternatives for requests with intermediate waypoints."""
    body = request_body(q)
    body["computeAlternativeRoutes"] = False
    del body["polylineEncoding"]
    stops = []
    for g in groups[:-1]:
        lat, lng = g.get("stop") or g["end"]
        loc = {"latLng": {"latitude": lat, "longitude": lng}}
        if g.get("heading") is not None:
            loc["heading"] = g["heading"]
        stops.append({"via": False, "location": loc})
    body["intermediates"] = stops
    return body


def done_keys(records: list) -> set:
    return {(r["route_id"], r["day"], r["slot_id"]) for r in records if r.get("status") == "ok"}


# =====================================================================
#  Response parsing
# =====================================================================
def _secs(v) -> int:
    return int(str(v or "0s").rstrip("s") or 0)


def parse_routes(api_json: dict) -> list:
    """Keep what later phases need; primary route = routes[0]."""
    out = []
    for rt in api_json.get("routes", []):
        legs = rt.get("legs", [])
        leg0, legN = (legs[0], legs[-1]) if legs else ({}, {})
        loc = lambda l, k: ((l.get(k) or {}).get("latLng") or {})
        point = lambda l, k: [loc(l, k).get("latitude"), loc(l, k).get("longitude")]
        steps = [{"distance_m": s.get("distanceMeters", 0),
                  "static_s": _secs(s.get("staticDuration")),
                  "start": point(s, "startLocation"), "end": point(s, "endLocation"),
                  "instruction": (s.get("navigationInstruction") or {}).get("instructions", ""),
                  "maneuver": (s.get("navigationInstruction") or {}).get("maneuver", "")}
                 for lg in legs for s in lg.get("steps", [])]
        out.append({
            "distance_m": rt.get("distanceMeters", 0),
            "duration_s": _secs(rt.get("duration")),
            "static_duration_s": _secs(rt.get("staticDuration")),
            "description": rt.get("description", ""),
            "route_labels": rt.get("routeLabels", []),
            "polyline": (rt.get("polyline") or {}).get("geoJsonLinestring", {}).get("coordinates", []),
            "start_location": [loc(leg0, "startLocation").get("latitude"), loc(leg0, "startLocation").get("longitude")],
            "end_location": [loc(legN, "endLocation").get("latitude"), loc(legN, "endLocation").get("longitude")],
            "steps": steps,
            "legs": [{"distance_m": lg.get("distanceMeters", 0), "duration_s": _secs(lg.get("duration")),
                      "static_duration_s": _secs(lg.get("staticDuration")),
                      "start": point(lg, "startLocation"), "end": point(lg, "endLocation")} for lg in legs],
        })
    return out


# =====================================================================
#  Real API call (PAID) and mock
# =====================================================================
def call_google(q: dict, api_key: str, body: dict = None, field_mask: str = None) -> tuple:
    """Returns (status, parsed_routes | None, error_text | None, http_status)."""
    import requests
    headers = {"Content-Type": "application/json", "X-Goog-Api-Key": api_key,
               "X-Goog-FieldMask": field_mask or C.V2_GMAPS_FIELD_MASK}
    body = body or request_body(q)
    for attempt in range(1, 6):
        try:
            r = requests.post(C.GMAPS_ROUTES_URL, headers=headers, json=body, timeout=60)
        except requests.RequestException as e:
            err, http = f"network error: {e}", 0
        else:
            if r.status_code == 200:
                routes = parse_routes(r.json())
                if not routes:
                    return "error", None, "no route returned", 200
                return "ok", routes, None, 200
            err, http = r.text, r.status_code
            if is_fatal_error(http, err):
                return "fatal", None, friendly_api_error(http, err), http
            if http not in (429, 500, 502, 503, 504):
                return "error", None, friendly_api_error(http, err), http
        wait = min(60, 2 ** attempt)
        print(f"    retry {attempt}/5 in {wait}s ({friendly_api_error(http, err)[:80]})")
        time.sleep(wait)
    return "error", None, friendly_api_error(http, err), http


_MOCK_FACTOR = {"AM_PEAK": 1.65, "MID_DAY": 1.30, "PM_PEAK": 1.85, "NIGHT": 1.00}


def call_mock(q: dict, geom: dict, route_row) -> tuple:
    """Offline stand-in built from the provisional OSM path. For testing the pipeline only."""
    coords = geom[q["route_id"]]
    length = float(route_row.osm_m)
    static = length / (28 / 3.6)
    noise = 0.92 + (stable_hash(q["route_id"], q["day"], q["slot_id"]) % 1000) / 1000 * 0.16
    wk = 0.85 if q["day"] in C.V2_WEEKEND_DAYS else 1.0
    live = static * (1 + (_MOCK_FACTOR[q["slot_id"]] - 1) * wk) * noise
    names = [n for n in str(route_row.osm_road_names).split(" | ") if n and n != "nan"] or ["Unnamed Road"]
    at = lambda f: list(reversed(coords[min(int(f * len(coords)), len(coords) - 1)]))   # [lat, lng] part-way along
    steps = [{"distance_m": int(length / len(names)), "static_s": int(static / len(names)),
              "start": at(i / len(names)), "end": at((i + 1) / len(names)),
              "maneuver": "TURN_LEFT" if i else "DEPART",
              "instruction": (f"Turn left onto {n}" if i else f"Head north on {n}")} for i, n in enumerate(names)]
    return "ok", [{
        "distance_m": int(length), "duration_s": int(live), "static_duration_s": int(static),
        "description": " and ".join(names[:2]), "route_labels": ["DEFAULT_ROUTE"], "polyline": coords,
        "start_location": [coords[0][1], coords[0][0]], "end_location": [coords[-1][1], coords[-1][0]],
        "steps": steps,
        "legs": [{"distance_m": int(length), "duration_s": int(live), "static_duration_s": int(static),
                  "start": [coords[0][1], coords[0][0]], "end": [coords[-1][1], coords[-1][0]]}]}], None, 200


def mock_subroutes(q: dict, whole_route: dict, groups: list) -> tuple:
    """Offline stand-in for the stopover request: splits the whole-route time by distance, plus a small stop cost."""
    scale = whole_route["duration_s"] / max(whole_route["distance_m"], 1)
    legs = [{"distance_m": g["distance_m"], "duration_s": int(g["distance_m"] * scale) + 10,
             "static_duration_s": g["static_duration_s"], "start": g["start"], "end": g["end"]} for g in groups]
    return "ok", [{"distance_m": sum(l["distance_m"] for l in legs), "duration_s": sum(l["duration_s"] for l in legs),
                   "static_duration_s": sum(l["static_duration_s"] for l in legs), "legs": legs}], None, 200


# =====================================================================
#  Round 2: sub-routes (a second request per query, built from the whole-route answers)
# =====================================================================
def subroute_queries(queries: list, jsonl) -> list:
    whole = {(r["route_id"], r["day"], r["slot_id"]): r for r in read_jsonl(jsonl) if r.get("status") == "ok"}
    out = []
    for q in queries:
        rec = whole.get((q["route_id"], q["day"], q["slot_id"]))
        if rec:
            rt = rec["routes"][0]
            groups = subroute_groups(rt["steps"])
            for g in groups:
                g["stop"], g["heading"] = stop_point(rt["polyline"], g["end"], C.V2_SUBROUTE_STOP_OFFSET_M[0])
            out.append({**q, "groups": groups, "polyline": rt["polyline"], "whole_route": {
                k: rt[k] for k in ("distance_m", "duration_s", "static_duration_s")}})
    return out


def run_subroutes(args, queries: list, d) -> None:
    if C.V2_ROUND != "2":
        sys.exit("--part subroutes exists only for Round 2 (set BENCHMARK_ROUND=2).")
    jsonl = d / C.V2_GMAPS_SUBROUTE_RESPONSES_JSONL
    items = subroute_queries(queries, d / C.V2_GMAPS_RESPONSES_JSONL)
    done = done_keys(read_jsonl(jsonl))
    pending = [q for q in items if (q["route_id"], q["day"], q["slot_id"]) not in done]
    todo = pending[: args.limit] if args.limit else pending
    calls = sum(1 for q in todo if len(q["groups"]) > 1)
    n = pd.Series([len(q["groups"]) for q in items] or [0])
    print(f"Sub-routes: {len(items)} of {len(queries)} whole-route answers available | done: {len(done)} | "
          f"pending: {len(pending)} | sub-routes per query: median {n.median():.0f}, max {n.max()}")
    print(f"Output: {jsonl}{'  [MOCK]' if args.mock else ''}")
    print(f"This run would make {calls} Routes API calls (queries on a single road need no second call).")
    if args.status:
        return
    if args.dry_run:
        if todo:
            print(f"Sample field mask: {C.V2_GMAPS_SUBROUTE_FIELD_MASK}")
            print(json.dumps(subroute_body(todo[0], todo[0]["groups"]), indent=2))
        print("DRY RUN — no network calls made.")
        return
    earliest = min((dt.datetime.fromisoformat(q["departure_ist"]) for q in todo), default=None)
    if not args.mock and earliest and earliest < dt.datetime.now(UTC) + dt.timedelta(minutes=C.V2_MIN_LEAD_MINUTES):
        sys.exit(f"Reference week has (partly) passed: earliest pending departure {earliest}.")
    api_key = None if args.mock else load_env_key(C.GMAPS_API_KEY_ENV)
    consecutive_err = 0
    for i, q in enumerate(todo, 1):
        t0 = time.time()
        groups = q["groups"]
        body = subroute_body(q, groups)
        if len(groups) == 1:
            w = q["whole_route"]
            status, routes_out, err, http = "ok", [{**w, "legs": [{**{k: w[k] for k in w}, "start": groups[0]["start"],
                                                                  "end": groups[0]["end"]}]}], None, None
        elif args.mock:
            whole = {**q["whole_route"]}
            status, routes_out, err, http = mock_subroutes(q, whole, groups)
        else:
            status, routes_out, err, http = call_google(q, api_key, body, C.V2_GMAPS_SUBROUTE_FIELD_MASK)
            off = (routes_out[0]["distance_m"] / max(q["whole_route"]["distance_m"], 1) - 1) if routes_out else 0
            if status == "ok" and abs(off) > C.V2_SUBROUTE_MAX_DIST_DIFF:     # detour at a stop: move stops further in
                first = {"distance_diff": round(off, 4), "request": body, "routes": routes_out}
                for g in groups:
                    g["stop"], g["heading"] = stop_point(q["polyline"], g["end"], C.V2_SUBROUTE_STOP_OFFSET_M[1])
                body = subroute_body(q, groups)
                status, routes_out, err, http = call_google(q, api_key, body, C.V2_GMAPS_SUBROUTE_FIELD_MASK)
                q = {**q, "first_attempt": first}
        rec = {k: q[k] for k in ("route_id", "day", "slot_id", "slot_time", "departure_ist", "departure_utc",
                                 "groups", "whole_route")}
        rec.update({"status": "ok" if status == "ok" else "error", "error": err, "http_status": http,
                    "routes": routes_out, "request": body, "single_road_no_call": len(groups) == 1,
                    "first_attempt": q.get("first_attempt"),
                    "distance_diff": round(routes_out[0]["distance_m"] / max(q["whole_route"]["distance_m"], 1) - 1, 4)
                    if routes_out else None,
                    "query_timestamp": dt.datetime.now(IST).isoformat(timespec="seconds"),
                    "latency_s": round(time.time() - t0, 2), "mock": args.mock, "traffic_semantics": "predicted"})
        append_jsonl(jsonl, rec)
        tag = "OK " if status == "ok" else "ERR"
        summary = (f"{len(groups)} sub-routes, {routes_out[0]['duration_s'] / 60:.0f} min vs whole "
                   f"{q['whole_route']['duration_s'] / 60:.0f} min") if routes_out else err
        print(f"[{i}/{len(todo)}] {tag} {q['route_id']} {q['day'][:3]} {q['slot_id']:8s} {summary}")
        if status == "fatal":
            print(f"STOPPED: configuration problem -> {err}")
            break
        consecutive_err = consecutive_err + 1 if status != "ok" else 0
        if consecutive_err >= 5:
            print("STOPPED: 5 consecutive errors — check the messages above.")
            break
        if not args.mock and len(groups) > 1:
            time.sleep(0.05)


# =====================================================================
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true", help="count, cost, sample request; no network")
    ap.add_argument("--limit", type=int, help="make at most N new queries (e.g. 1 for a test)")
    ap.add_argument("--mock", action="store_true", help="offline fake responses into data/benchmark_v2/mock/")
    ap.add_argument("--status", action="store_true", help="progress summary; no network")
    ap.add_argument("--part", choices=["whole", "subroutes"], default="whole", help="Round 2: see the note above")
    args = ap.parse_args()

    routes = pd.read_csv(C.V2_OD_PAIRS_CSV)
    d = out_dir(args.mock)
    jsonl = d / C.V2_GMAPS_RESPONSES_JSONL
    man = load_or_create_manifest(d, args.mock, create=not (args.dry_run or args.status))
    queries = build_queries(routes, man)
    if args.part == "subroutes":
        return run_subroutes(args, queries, d)
    records = read_jsonl(jsonl)
    done = done_keys(records)
    pending = [q for q in queries if (q["route_id"], q["day"], q["slot_id"]) not in done]
    n_err = sum(1 for r in records if r.get("status") != "ok")

    print(f"Routes: {len(routes)} | queries: {len(queries)} (= routes × {len(C.V2_DAYS)} days × {len(C.TIME_SLOTS)} slots)")
    print(f"Output: {jsonl}{'  [MOCK]' if args.mock else ''}")
    print(f"Done OK: {len(done)} | pending: {len(pending)} | error records so far: {n_err}")
    print(f"Reference week: Monday {man['reference_monday']} (IST) · routing {man['routing_preference']}"
          f"{' · trafficModel ' + man['traffic_model'] if man['traffic_model'] else ''} · alternatives {man['compute_alternatives']}")
    first_dep = min(dt.datetime.fromisoformat(q["departure_ist"]) for q in queries)
    deadline = first_dep - dt.timedelta(minutes=C.V2_MIN_LEAD_MINUTES)
    print(f"Deadline: every query must be sent before {deadline:%a %d %b %Y %H:%M} IST "
          f"(first departure {first_dep:%a %d %b %H:%M})")
    notes = {d: n for d, n in C.V2_CALENDAR_NOTES.items()}
    if notes:
        print("Calendar notes in this week: " + "; ".join(f"{d}: {n}" for d, n in notes.items()))
    if args.status:
        return

    todo = pending[: args.limit] if args.limit else pending
    if args.dry_run or not args.mock:
        cost_list = len(todo) * C.V2_ROUTES_PRICE_PER_CALL
        print(f"This run would make {len(todo)} Routes API calls (Compute Routes Pro SKU). List price "
              f"${cost_list:.2f}; first {C.V2_ROUTES_FREE_PER_MONTH:,}/month free -> expected $0 "
              f"unless the billing account already used Routes this month.")
    if args.dry_run:
        if todo:
            print("Sample request body (key goes in a header, not shown):")
            print(json.dumps(request_body(todo[0]), indent=2))
        print("DRY RUN — no network calls made.")
        return

    # Every departure must still be in the future (the manifest week is fixed).
    now_utc = dt.datetime.now(UTC)
    earliest = min((dt.datetime.fromisoformat(q["departure_ist"]) for q in todo), default=None)
    if earliest and earliest < now_utc + dt.timedelta(minutes=C.V2_MIN_LEAD_MINUTES):
        sys.exit(f"Reference week has (partly) passed: earliest pending departure {earliest}. "
                 f"Move {d} aside to start a new run with a new week.")

    if args.mock:
        import geopandas as gpd
        g = gpd.read_file(C.V2_OD_PAIRS_GEOJSON)
        geom = {r.route_id: [list(c) for c in r.geometry.coords] for r in g.itertuples()}
        rows = routes.set_index("route_id")
    else:
        api_key = load_env_key(C.GMAPS_API_KEY_ENV)

    made, consecutive_err = 0, 0
    for i, q in enumerate(todo, 1):
        t0 = time.time()
        if args.mock:
            status, routes_out, err, http = call_mock(q, geom, rows.loc[q["route_id"]])
        else:
            status, routes_out, err, http = call_google(q, api_key)
        made += 1
        rec = {k: q[k] for k in ("route_id", "day", "slot_id", "slot_time", "departure_ist", "departure_utc")}
        rec.update({"status": "ok" if status == "ok" else "error", "error": err, "http_status": http,
                    "routes": routes_out, "n_routes": len(routes_out or []),
                    "request": {k: v for k, v in request_body(q).items()},
                    "query_timestamp": dt.datetime.now(IST).isoformat(timespec="seconds"),
                    "latency_s": round(time.time() - t0, 2), "mock": args.mock,
                    "traffic_semantics": "predicted"})
        append_jsonl(jsonl, rec)
        tag = "OK " if status == "ok" else "ERR"
        summary = (f"{routes_out[0]['distance_m'] / 1000:.1f} km, {routes_out[0]['duration_s'] / 60:.0f} min "
                   f"(static {routes_out[0]['static_duration_s'] / 60:.0f})") if routes_out else err
        print(f"[{i}/{len(todo)}] {tag} {q['route_id']} {q['day'][:3]} {q['slot_id']:8s} {summary}")
        if status == "fatal":
            print(f"STOPPED: configuration problem -> {err}")
            break
        consecutive_err = consecutive_err + 1 if status != "ok" else 0
        if consecutive_err >= 5:
            print("STOPPED: 5 consecutive errors — check the messages above.")
            break
        if not args.mock:
            time.sleep(0.05)
    print(f"Calls made this run: {made}{' (mock, no network)' if args.mock else ''}")


if __name__ == "__main__":
    main()
