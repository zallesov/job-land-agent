#!/usr/bin/env python3
"""
List newly inserted jobs per provider for kanban task creation.

Outputs JSON with per-provider summary: count, sample titles, job IDs.
Used by the pipeline to create kanban research tasks after ingest.

Usage:
  python3 scripts/list_new_jobs.py --db jobs.db [--provider wellfound]
"""
import argparse
import json
import sqlite3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=PROJECT_ROOT / "jobs.db")
    parser.add_argument("--provider", help="Filter to specific provider")
    args = parser.parse_args()

    db = sqlite3.connect(str(args.db))
    db.row_factory = sqlite3.Row

    query = """
        SELECT provider, id, title, posted_company_name, location, salary_range, url
        FROM jobs
        WHERE status = 'new'
          AND deleted_at IS NULL
    """
    params: list = []
    if args.provider:
        query += " AND provider = ?"
        params.append(args.provider)

    query += " ORDER BY provider, id"
    cur = db.execute(query, params)
    rows = cur.fetchall()

    if not rows:
        print(json.dumps({"providers": {}, "total": 0}))
        db.close()
        return 0

    by_provider: dict[str, dict] = {}
    for row in rows:
        p = row["provider"]
        if p not in by_provider:
            by_provider[p] = {"count": 0, "job_ids": [], "samples": []}
        by_provider[p]["count"] += 1
        by_provider[p]["job_ids"].append(row["id"])
        if len(by_provider[p]["samples"]) < 5:
            by_provider[p]["samples"].append({
                "id": row["id"],
                "company": row["posted_company_name"] or "?",
                "title": row["title"] or "?",
                "salary": row["salary_range"] or "",
                "url": row["url"] or "",
            })

    output = {"providers": by_provider, "total": len(rows)}
    print(json.dumps(output, indent=2))
    db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
