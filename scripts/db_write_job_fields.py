#!/usr/bin/env python3
"""
Update job fields from JSON (stdin) after URL scrape.

Usage:
  echo '<json>' | python3 db_write_job_fields.py --job-id 123

--db is accepted but ignored (PocketBase config comes from .env).
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from scripts.pb_client import get_pb

UPDATABLE_FIELDS = [
    "title", "posted_company_name", "location", "country",
    "remote_scope", "description", "apply_url", "date_posted",
]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", help="(ignored — PocketBase is used)")
    parser.add_argument("--job-id", required=True, dest="job_id")
    args = parser.parse_args()

    try:
        data = json.load(sys.stdin)
    except json.JSONDecodeError as e:
        print(f"ERROR: invalid JSON: {e}", file=sys.stderr)
        return 1

    pb = get_pb()
    updates = {k: data[k] for k in UPDATABLE_FIELDS if k in data and data[k] is not None}
    if updates:
        pb.update_job(args.job_id, **updates)
        pb.log_event(
            "job", args.job_id, "fields_scraped", "hermes_scrape",
            json.dumps({"fields": list(updates.keys())}),
        )
        print(f"Updated: {', '.join(updates.keys())}", file=sys.stderr)
    else:
        print("No fields to update", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
