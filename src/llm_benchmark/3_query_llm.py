import os
import csv
import json
import time
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

from google import genai
from google.genai import types

from config import (
    BENCHMARK_ROUTES_GEOCODED_CSV,
    SYSTEM_PROMPT_FILE,
    MODELS,
    ACTIVE_MODEL,
    TIME_SLOTS,
    DAY_TYPES,
    LLM_RESPONSES_DIR
)

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


def append_record(output_file: Path, record: dict):
    """Append a single record to the JSONL file immediately after each query."""
    with open(output_file, 'a', encoding='utf-8') as f:
        f.write(json.dumps(record) + '\n')


def load_existing_keys(output_file: Path) -> set:
    """Load already-completed (sub_route_id, time_slot, day_type) keys so we can resume."""
    done = set()
    if not output_file.exists():
        return done
    with open(output_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
                done.add((r['sub_route_id'], r['time_slot'], r['day_type']))
            except Exception:
                pass
    return done


def main():
    env_path = Path(__file__).resolve().parent.parent.parent / '.env'
    load_dotenv(dotenv_path=env_path)

    model_config = MODELS.get(ACTIVE_MODEL)
    if not model_config:
        print(f"Error: Active model '{ACTIVE_MODEL}' not found in config.MODELS")
        return

    api_key = os.getenv(model_config['api_key_env'])
    if not api_key:
        print(f"Error: {model_config['api_key_env']} not found in .env")
        return

    client = genai.Client(api_key=api_key)
    model_name = model_config['model_name']

    try:
        with open(SYSTEM_PROMPT_FILE, 'r', encoding='utf-8') as f:
            system_prompt = f.read().strip()
    except FileNotFoundError:
        print(f"Error: {SYSTEM_PROMPT_FILE} not found.")
        return

    try:
        with open(BENCHMARK_ROUTES_GEOCODED_CSV, 'r', encoding='utf-8') as f:
            routes = list(csv.DictReader(f))
    except FileNotFoundError:
        print(f"Error: {BENCHMARK_ROUTES_GEOCODED_CSV} not found. Run 2_reverse_geocode.py first.")
        return

    LLM_RESPONSES_DIR.mkdir(parents=True, exist_ok=True)

    # Output file: JSONL (one JSON object per line) — safe to resume from
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = LLM_RESPONSES_DIR / f"{ACTIVE_MODEL}_{timestamp}.jsonl"

    # Resume support: skip already-completed queries if a prior run was interrupted
    # To resume a specific file, pass its path as an argument or rename it here.
    done_keys = set()
    prior_files = sorted(LLM_RESPONSES_DIR.glob(f"{ACTIVE_MODEL}_*.jsonl"))
    if prior_files:
        latest = prior_files[-1]
        done_keys = load_existing_keys(latest)
        if done_keys:
            output_file = latest  # append to the existing file
            print(f"Resuming from {latest.name} — {len(done_keys)} queries already done, skipping them.")

    total_queries = len(routes) * len(TIME_SLOTS) * len(DAY_TYPES)
    current_query = 0
    saved_count = 0

    print(f"Model      : {model_name}  (thinking disabled for speed)")
    print(f"Total      : {total_queries} queries  ({len(routes)} routes × {len(TIME_SLOTS)} slots × {len(DAY_TYPES)} day types)")
    print(f"Output     : {output_file}")
    print("-" * 70)

    for route in routes:
        origin_name      = route['origin_name']
        destination_name = route['destination_name']
        sub_route_id     = route['sub_route_id']

        for time_slot in TIME_SLOTS:
            for day_type in DAY_TYPES:
                current_query += 1
                time_id   = time_slot['id']
                time_label = time_slot['label']
                day_label  = 'Wednesday' if day_type == 'WEEKDAY' else 'Saturday'

                key = (sub_route_id, time_id, day_type)
                if key in done_keys:
                    print(f"[{current_query}/{total_queries}] SKIP (already done): {origin_name} → {destination_name} | {time_id} | {day_type}")
                    continue

                print(f"[{current_query}/{total_queries}] Querying: {origin_name} → {destination_name} | {time_id} | {day_type}", end='', flush=True)

                prompt_text = (
                    f"Origin: {origin_name}\n"
                    f"Destination: {destination_name}\n"
                    f"City: Bangalore, India\n"
                    f"Day of the week: {day_label}\n"
                    f"Time of day: {time_label}"
                )

                parsed_json = None
                raw_response = None
                t0 = time.time()

                max_attempts = 6  # more attempts to ride out rate limits
                for attempt in range(max_attempts):
                    try:
                        response = client.models.generate_content(
                            model=model_name,
                            contents=prompt_text,
                            config=types.GenerateContentConfig(
                                response_mime_type='application/json',
                                response_json_schema=ROUTE_SCHEMA,
                                system_instruction=system_prompt,
                                thinking_config=types.ThinkingConfig(thinking_budget=0),
                            ),
                        )
                        raw_response = response.text
                        parsed_json = json.loads(raw_response)
                        break
                    except Exception as e:
                        err_str = str(e)
                        is_rate_limit = '429' in err_str or 'RESOURCE_EXHAUSTED' in err_str
                        is_unavailable = '503' in err_str or 'UNAVAILABLE' in err_str

                        # Try to parse the suggested retryDelay from the API error
                        wait_s = 60  # default fallback
                        if 'retryDelay' in err_str:
                            import re
                            match = re.search(r"'retryDelay':\s*'(\d+)s'", err_str)
                            if match:
                                wait_s = int(match.group(1)) + 5  # add buffer

                        if is_rate_limit:
                            print(f"\n  [Rate limit] Waiting {wait_s}s before retry {attempt + 1}/{max_attempts}...", flush=True)
                            time.sleep(wait_s)
                        elif is_unavailable:
                            print(f"\n  [Unavailable] Waiting 30s before retry {attempt + 1}/{max_attempts}...", flush=True)
                            time.sleep(30)
                        else:
                            print(f"\n  Attempt {attempt + 1} failed: {e}")
                            if attempt >= 2:
                                break  # give up on genuine errors after 3
                            time.sleep(5)

                elapsed = time.time() - t0
                print(f"  ✓ {elapsed:.1f}s")

                record = {
                    "sub_route_id":    sub_route_id,
                    "origin_name":     origin_name,
                    "destination_name": destination_name,
                    "time_slot":       time_id,
                    "day_type":        day_type,
                    "model":           ACTIVE_MODEL,
                    "prompt":          prompt_text,
                    "raw_response":    raw_response,
                    "parsed_response": parsed_json,
                    "query_timestamp": datetime.now().isoformat(),
                }

                # ✅ Write to disk immediately after every query
                append_record(output_file, record)
                saved_count += 1

                time.sleep(0.5)  # reduced delay since thinking is off

    print("-" * 70)
    print(f"Done. {saved_count} new queries saved → {output_file}")
    print(f"Total records in file: {saved_count + len(done_keys)}")


if __name__ == "__main__":
    main()
