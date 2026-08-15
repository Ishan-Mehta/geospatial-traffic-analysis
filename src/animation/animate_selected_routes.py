import argparse
import glob
import json
import re
import time
from datetime import datetime, timedelta
from pathlib import Path

class RouteTrafficProcessor:
    def __init__(self, route_name, tolerance=0):
        self.route_name = route_name
        self.tolerance = tolerance
        self.historical_records = [] 
        self.speed_map = {"NORMAL": 1, "SLOW": 2, "TRAFFIC_JAM": 3}

    def process_entry(self, entry):
        from shapely.geometry import LineString

        timestamp = normalize_timestamp(entry.get("request_timestamp", ""))
        if not timestamp:
            return False

        routes = entry.get("api_response", {}).get("routes", [])
        if not routes:
            return False

        route = routes[0]
        legs = route.get("legs", [])
        if not legs:
            return False

        added_any = False
        seq = 0

        # Process intervals per leg rather than per route
        for leg in legs:
            leg_coords = leg.get("polyline", {}).get("geoJsonLinestring", {}).get("coordinates", [])
            if not leg_coords:
                continue

            intervals = leg.get("travelAdvisory", {}).get("speedReadingIntervals", [])
            
            for interval in intervals:
                start_idx = interval.get("startPolylinePointIndex", 0)
                end_idx = interval.get("endPolylinePointIndex", 0)
                speed_text = interval.get("speed", "NORMAL")
                speed_val = self.speed_map.get(speed_text, 1)

                segment_coords = leg_coords[start_idx:end_idx + 1]
                if len(segment_coords) < 2:
                    continue

                line = LineString(segment_coords)
                if self.tolerance > 0:
                    line = line.simplify(self.tolerance, preserve_topology=True)

                self.historical_records.append({
                    "segment_seq": seq,
                    "route_name": self.route_name,
                    "start_time": timestamp,
                    "end_time": None,  # computed in finalize_and_export
                    "speed_colour": speed_val,
                    "geometry": line,
                })
                seq += 1
                added_any = True

        return added_any

    def finalize_and_export(self, output_gpkg):
        import geopandas as gpd
        import pandas as pd

        if not self.historical_records:
            return False

        unique_timestamps = sorted(
            set(rec["start_time"] for rec in self.historical_records)
        )

        end_time_map = {}
        for i in range(len(unique_timestamps) - 1):
            end_time_map[unique_timestamps[i]] = unique_timestamps[i + 1]

        if len(unique_timestamps) > 1:
            intervals_sec = [
                (
                    datetime.strptime(unique_timestamps[i + 1], "%Y-%m-%d %H:%M:%S")
                    - datetime.strptime(unique_timestamps[i], "%Y-%m-%d %H:%M:%S")
                ).total_seconds()
                for i in range(len(unique_timestamps) - 1)
            ]
            median_interval = sorted(intervals_sec)[len(intervals_sec) // 2]
        else:
            median_interval = 7200  

        last_end = (
            datetime.strptime(unique_timestamps[-1], "%Y-%m-%d %H:%M:%S")
            + timedelta(seconds=median_interval)
        ).strftime("%Y-%m-%d %H:%M:%S")
        end_time_map[unique_timestamps[-1]] = last_end

        for rec in self.historical_records:
            rec["end_time"] = end_time_map[rec["start_time"]]

        df = pd.DataFrame(self.historical_records)
        df["start_time"] = pd.to_datetime(df["start_time"])
        df["end_time"] = pd.to_datetime(df["end_time"])

        gdf = gpd.GeoDataFrame(df, geometry="geometry", crs="EPSG:4326")
        gdf.to_file(output_gpkg, driver="GPKG", layer="traffic_segments")

        return True


def normalize_timestamp(raw_timestamp):
    if not raw_timestamp:
        return ""
    base = raw_timestamp[:19].replace("T", " ")
    try:
        return datetime.strptime(base, "%Y-%m-%d %H:%M:%S").strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        return ""


def discover_routes(file_pattern):
    files = sorted(glob.glob(file_pattern))
    if not files:
        return []

    with open(files[0], "r") as f:
        data = json.load(f)

    route_names = []
    seen = set()
    for entry in data:
        name = entry.get("road_name")
        if name and name not in seen:
            route_names.append(name)
            seen.add(name)
    return route_names


def slugify(name):
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", name.strip()).strip("_")
    return slug[:80] if slug else "route"


def parse_selected_routes(route_numbers, route_names, discovered_routes):
    selected = set()

    if route_numbers:
        for token in route_numbers.split(","):
            token = token.strip()
            if not token:
                continue
            idx = int(token)
            if idx < 1 or idx > len(discovered_routes):
                raise ValueError(f"Route number {idx} is out of range 1..{len(discovered_routes)}")
            selected.add(discovered_routes[idx - 1])

    if route_names:
        for token in route_names.split(","):
            name = token.strip()
            if name:
                selected.add(name)

    return selected


def main():
    parser = argparse.ArgumentParser(
        description="Process only selected Bangalore routes and export one file per selected route."
    )
    parser.add_argument(
        "--file-pattern",
        default="../../data/raw/bangalore_routes_response_*.json",
        help="Glob pattern for source JSON files.",
    )
    parser.add_argument(
        "--list-routes",
        action="store_true",
        help="List discovered route numbers and names, then exit.",
    )
    parser.add_argument(
        "--routes",
        default="",
        help="Comma-separated route numbers (1-based) from --list-routes, e.g. 1,5,20",
    )
    parser.add_argument(
        "--route-names",
        default="",
        help="Comma-separated exact road names, e.g. 'Begur Main Road,Kudlu Road'",
    )
    parser.add_argument(
        "--output-dir",
        default="../../output/route_exports",
        help="Directory where per-route outputs are written.",
    )
    parser.add_argument(
        "--tolerance",
        type=float,
        default=0,
        help="Douglas-Peucker simplification tolerance (0 = no simplification, recommended).",
    )

    args = parser.parse_args()

    discovered_routes = discover_routes(args.file_pattern)
    if not discovered_routes:
        raise FileNotFoundError(f"No files found for pattern: {args.file_pattern}")

    if args.list_routes:
        print("Discovered routes (from first snapshot file):")
        for idx, name in enumerate(discovered_routes, start=1):
            print(f"{idx:3d}. {name}")
        return

    if not args.routes and not args.route_names:
        raise ValueError("Please provide --routes or --route-names (or use --list-routes).")

    selected_routes = parse_selected_routes(args.routes, args.route_names, discovered_routes)
    if not selected_routes:
        raise ValueError("No valid routes selected.")

    json_files = sorted(glob.glob(args.file_pattern))
    processors = {
        route_name: RouteTrafficProcessor(route_name=route_name, tolerance=args.tolerance)
        for route_name in selected_routes
    }

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    start_total = time.time()
    print(f"Processing {len(json_files)} files for {len(selected_routes)} selected routes...")

    for index, file_path in enumerate(json_files, start=1):
        file_start = time.time()
        with open(file_path, "r") as f:
            data = json.load(f)

        matched_entries = 0
        for entry in data:
            route_name = entry.get("road_name")
            if route_name not in selected_routes:
                continue

            if processors[route_name].process_entry(entry):
                matched_entries += 1

        elapsed = time.time() - file_start
        print(f"[{index}/{len(json_files)}] {Path(file_path).name}: matched {matched_entries} entries in {elapsed:.2f}s")

    print("Exporting per-route outputs...")

    for idx, route_name in enumerate(sorted(selected_routes), start=1):
        processor = processors[route_name]
        route_slug = slugify(route_name)
        base_name = f"route_{idx:03d}_{route_slug}"
        output_gpkg = output_dir / f"{base_name}.gpkg"

        ok = processor.finalize_and_export(
            output_gpkg=str(output_gpkg),
        )

        if ok:
            print(f"  ✅ {route_name} -> {output_gpkg.name}")
        else:
            print(f"  ⚠️ {route_name} -> no geometry/state data found, skipped export")

    total_elapsed = time.time() - start_total
    print(f"Done in {total_elapsed / 60:.2f} minutes.")


if __name__ == "__main__":
    main()