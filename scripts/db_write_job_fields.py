#!/usr/bin/env python3
"""
Update job fields from JSON (stdin) after URL scrape.

Usage:
  echo '<json>' | python3 db_write_job_fields.py --db jobs.db --job-id 123
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from db import get_connection, log_event

UPDATABLE_FIELDS = [
    "title", "posted_company_name", "location", "country",
    "remote_scope", "description", "apply_url", "date_posted",
]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", required=True)
    parser.add_argument("--job-id", type=int, required=True)
    args = parser.parse_args()

    try:
        data = json.load(sys.stdin)
    except json.JSONDecodeError as e:
        print(f"ERROR: invalid JSON: {e}", file=sys.stderr)
        return 1

    con = get_connection(args.db)
    updates = {k: data[k] for k in UPDATABLE_FIELDS if k in data and data[k] is not None}
    if updates:
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        params = list(updates.values()) + [args.job_id]
        con.execute(
            f"UPDATE jobs SET {set_clause}, updated_at = datetime('now') WHERE id = ?",
            params,
        )
        log_event(
            con, "job", args.job_id, "fields_scraped", "hermes_scrape",
            json.dumps({"fields": list(updates.keys())}),
        )
        con.commit()
        print(f"Updated: {', '.join(updates.keys())}", file=sys.stderr)
    else:
        print("No fields to update", file=sys.stderr)

    con.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
