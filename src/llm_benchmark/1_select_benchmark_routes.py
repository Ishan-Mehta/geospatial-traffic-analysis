"""
Step 1: Select Benchmark Routes

Reads the ranked analysis CSVs from output/results/, picks the top/bottom N
routes from each configured category, de-duplicates, and joins with the master
subroutes CSV to get coordinates.

Output: data/benchmark/benchmark_routes.csv
"""

import pandas as pd
from config import (
    SELECTION,
    ANALYSIS_RESULTS_DIR,
    MASTER_SUBROUTES_CSV,
    BENCHMARK_ROUTES_CSV,
    COMMON_COLUMNS,
)


def load_ranked_csv(filename: str) -> pd.DataFrame:
    """Load a ranked CSV, drop the rank column, and return with standard columns."""
    path = ANALYSIS_RESULTS_DIR / filename
    df = pd.read_csv(path)

    # The first column is always the rank column (e.g. delay_rank, distance_rank).
    # Drop it — we'll use row position instead.
    rank_col = df.columns[0]
    df = df.drop(columns=[rank_col])

    return df


def select_routes() -> pd.DataFrame:
    """
    For each category in SELECTION, pick the configured number of routes.
    Returns a de-duplicated DataFrame with a 'category' column.
    """
    all_selected = []

    for category, (count, csv_file, order) in SELECTION.items():
        df = load_ranked_csv(csv_file)

        if order == "top":
            picked = df.head(count).copy()
        elif order == "bottom":
            picked = df.tail(count).copy()
        else:
            raise ValueError(f"Unknown sort order '{order}' for category '{category}'")

        picked["category"] = category
        all_selected.append(picked)
        print(f"  [{category}] picked {len(picked)} routes from {csv_file} ({order})")

    combined = pd.concat(all_selected, ignore_index=True)

    # De-duplicate: a route may appear in multiple categories.
    # Keep the first occurrence's category (the one listed first in SELECTION).
    before = len(combined)
    combined = combined.drop_duplicates(subset="sub_route_id", keep="first")
    after = len(combined)

    if before != after:
        print(f"\n  De-duplicated: {before} → {after} unique routes")

    return combined


def join_with_coordinates(selected: pd.DataFrame) -> pd.DataFrame:
    """
    Join selected routes with the master subroutes CSV to get
    start/end coordinates.
    """
    master = pd.read_csv(MASTER_SUBROUTES_CSV)

    # Master has: sub_route_id, start_lat, start_lng, end_lat, end_lng,
    #             distance_meters, static_duration_s
    # We want the coordinates — distance is already in selected from the ranked CSV.
    coord_cols = ["sub_route_id", "start_lat", "start_lng", "end_lat", "end_lng"]
    merged = selected.merge(master[coord_cols], on="sub_route_id", how="left")

    missing = merged["start_lat"].isna().sum()
    if missing > 0:
        print(f"\n  ⚠️  {missing} routes could not be matched to coordinates!")

    return merged


def main():
    print("=" * 60)
    print("STEP 1 — SELECT BENCHMARK ROUTES")
    print("=" * 60)

    # 1. Select from ranked CSVs
    print("\nSelecting routes per category:")
    selected = select_routes()

    # 2. Join with coordinates
    print("\nJoining with master subroutes for coordinates...")
    result = join_with_coordinates(selected)

    # 3. Reorder columns for clarity
    output_columns = [
        "sub_route_id", "category", "road_name",
        "start_lat", "start_lng", "end_lat", "end_lng",
        "distance_meters", "avg_live_duration_s", "avg_delay_s",
        "avg_congestion_ratio", "ratio_std_dev", "avg_speed_kmph",
        "snapshot_count",
    ]
    # Only keep columns that actually exist (safety)
    output_columns = [c for c in output_columns if c in result.columns]
    result = result[output_columns]

    # 4. Save
    BENCHMARK_ROUTES_CSV.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(BENCHMARK_ROUTES_CSV, index=False)

    # 5. Summary
    print(f"\n{'=' * 60}")
    print(f"DONE — {len(result)} benchmark routes saved to:")
    print(f"  {BENCHMARK_ROUTES_CSV}")
    print(f"{'=' * 60}")

    print(f"\nBreakdown by category:")
    print(result["category"].value_counts().to_string())

    print(f"\nDistance range: {result['distance_meters'].min():.0f}m – {result['distance_meters'].max():.0f}m")
    print(f"Avg delay range: {result['avg_delay_s'].min():.1f}s – {result['avg_delay_s'].max():.1f}s")

    # Preview
    print(f"\nPreview (first 5 rows):")
    print(result[["sub_route_id", "category", "road_name", "distance_meters", "avg_delay_s"]].head().to_string(index=False))


if __name__ == "__main__":
    main()
