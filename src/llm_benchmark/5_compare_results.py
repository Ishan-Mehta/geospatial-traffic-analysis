import json
import csv
from pathlib import Path
import difflib

from config import (
    LLM_RESPONSES_DIR,
    GMAPS_RESPONSES_DIR,
    BENCHMARK_ROUTES_CSV,
    COMPARISON_RESULTS_DIR
)

def find_latest_json(directory, prefer_ext=None):
    """Find the most recently modified JSON or JSONL file in a directory."""
    files = list(directory.glob("*.json")) + list(directory.glob("*.jsonl"))
    if not files:
        return None
    return max(files, key=lambda p: p.stat().st_mtime)


def load_responses(filepath: Path) -> list:
    """Load either a plain JSON array or a JSONL file."""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read().strip()
    if filepath.suffix == '.jsonl' or (content and content[0] == '{'):
        # JSONL — one record per line
        records = []
        for line in content.splitlines():
            line = line.strip()
            if line:
                records.append(json.loads(line))
        return records
    return json.loads(content)

def get_route_metadata():
    metadata = {}
    if not BENCHMARK_ROUTES_CSV.exists():
        return metadata
    with open(BENCHMARK_ROUTES_CSV, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            metadata[row['sub_route_id']] = {
                'category': row.get('category', ''),
                'road_name': row.get('road_name', '')
            }
    return metadata

def main():
    print("Starting comparison...")
    COMPARISON_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    
    llm_file = find_latest_json(LLM_RESPONSES_DIR)
    gmaps_file = find_latest_json(GMAPS_RESPONSES_DIR)
    
    if not llm_file or not gmaps_file:
        print("Missing LLM or GMaps response files. Run both querying scripts first.")
        return
        
    print(f"Using LLM file: {llm_file.name}")
    print(f"Using GMaps file: {gmaps_file.name}")
    
    with open(llm_file, 'r') as f:
        llm_data = load_responses(llm_file)
    with open(gmaps_file, 'r') as f:
        gmaps_data = load_responses(gmaps_file)
        
    # Index gmaps data by key
    gmaps_dict = {}
    for g in gmaps_data:
        key = (g['sub_route_id'], g['time_slot'], g['day_type'])
        gmaps_dict[key] = g
        
    metadata = get_route_metadata()
    
    comparisons = []
    
    for l in llm_data:
        sub_route_id = l.get('sub_route_id')
        time_slot = l.get('time_slot')
        day_type = l.get('day_type')
        model = l.get('model', 'unknown')
        
        key = (sub_route_id, time_slot, day_type)
        if key not in gmaps_dict:
            continue
            
        g = gmaps_dict[key]
        
        # Parsed LLM data is nested inside 'parsed_response'
        parsed = l.get('parsed_response', {}) or {}
        llm_dist_km = parsed.get('estimated_distance_km', 0)
        llm_time_min = parsed.get('estimated_time_minutes', 0)
        
        gmaps_dist_m = g.get('distance_m', 0)
        gmaps_live_s = g.get('live_duration_s', 0)
        gmaps_static_s = g.get('static_duration_s', 0)
        
        if gmaps_dist_m == 0 or gmaps_live_s == 0 or gmaps_static_s == 0:
            continue
            
        # compute metrics
        dist_error_pct = (llm_dist_km * 1000 - gmaps_dist_m) / gmaps_dist_m * 100
        time_vs_live_error_pct = (llm_time_min * 60 - gmaps_live_s) / gmaps_live_s * 100
        time_vs_static_error_pct = (llm_time_min * 60 - gmaps_static_s) / gmaps_static_s * 100
        abs_dist_error_km = abs(llm_dist_km - gmaps_dist_m / 1000)
        abs_time_error_min = abs(llm_time_min - gmaps_live_s / 60)
        
        # Route match
        llm_route = parsed.get('suggested_route', [])
        if isinstance(llm_route, list):
            llm_route_str = ", ".join(llm_route)
        else:
            llm_route_str = str(llm_route)
            
        gmaps_route_desc = g.get('route_description', '')
        
        route_match_score = difflib.SequenceMatcher(None, llm_route_str.lower(), gmaps_route_desc.lower()).ratio()
        
        meta = metadata.get(sub_route_id, {'category': 'unknown', 'road_name': 'unknown'})
        
        comparisons.append({
            'sub_route_id': sub_route_id,
            'road_name': meta['road_name'],
            'category': meta['category'],
            'time_slot': time_slot,
            'day_type': day_type,
            'model': model,
            'llm_route': llm_route_str,
            'llm_dist_km': llm_dist_km,
            'llm_time_min': llm_time_min,
            'llm_traffic_awareness': parsed.get('traffic_awareness', ''),
            'gmaps_dist_m': gmaps_dist_m,
            'gmaps_live_s': gmaps_live_s,
            'gmaps_static_s': gmaps_static_s,
            'gmaps_delay_s': g.get('delay_s', 0),
            'gmaps_route_desc': gmaps_route_desc,
            'dist_error_pct': dist_error_pct,
            'time_vs_live_error_pct': time_vs_live_error_pct,
            'time_vs_static_error_pct': time_vs_static_error_pct,
            'route_match_score': route_match_score,
            'abs_dist_error_km': abs_dist_error_km,
            'abs_time_error_min': abs_time_error_min
        })
        
    if not comparisons:
        print("No matching records found.")
        return
        
    comp_file = COMPARISON_RESULTS_DIR / 'benchmark_comparison.csv'
    with open(comp_file, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=comparisons[0].keys())
        writer.writeheader()
        writer.writerows(comparisons)
        
    print(f"Saved {len(comparisons)} comparisons to {comp_file}")
    
    # Compute summary stats
    try:
        import pandas as pd
        df = pd.DataFrame(comparisons)
        
        # Summarize by model, category, time_slot
        summary = df.groupby(['model', 'category', 'time_slot']).agg({
            'dist_error_pct': ['mean', 'median'],
            'time_vs_live_error_pct': ['mean', 'median'],
            'abs_dist_error_km': ['mean', 'median'],
            'abs_time_error_min': ['mean', 'median']
        }).reset_index()
        
        # Flatten columns
        summary.columns = ['_'.join(col).strip('_') for col in summary.columns.values]
        
        summary_file = COMPARISON_RESULTS_DIR / 'summary_stats.csv'
        summary.to_csv(summary_file, index=False)
        print(f"Saved summary stats to {summary_file}")
        
        print("\nSummary Table:")
        print(summary)
    except ImportError:
        print("pandas not found, skipping summary stats.")

if __name__ == "__main__":
    main()
