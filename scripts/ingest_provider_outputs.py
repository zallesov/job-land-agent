#!/usr/bin/env python3
"""
Ingest normalized provider JSON arrays into SQLite.

Usage:
  python3 ingest_provider_outputs.py --db jobs.db --run-file outputs/greenhouse/runs/greenhouse_jobs_live_2026-05-18.json
  python3 ingest_provider_outputs.py --db jobs.db --all-latest
"""
import argparse
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from db import (
    create_db, get_connection, upsert_company, get_job_by_url,
    insert_job, log_event, create_pipeline_run, finish_pipeline_run
)

PROVIDERS_DIR = Path(__file__).parent.parent / "outputs"


def _extract_domain(url: str | None) -> str | None:
    if not url:
        return None
    m = re.search(r"https?://(?:www\.)?([^/]+)", url)
    return m.group(1).lower() if m else None


def _detect_remote_scope(location: str, description: str) -> str:
    text = f"{location} {description}".lower()
    if "fully remote" in text or "100% remote" in text:
        return "remote"
    if "remote" in text and "hybrid" in text:
        return "hybrid"
    if "remote" in text:
        return "remote"
    if "on-site" in text or "onsite" in text or "in-office" in text:
        return "onsite"
    return "unknown"


def normalize_job(raw: dict) -> dict:
    known = {"provider", "company", "title", "url", "description",
             "applyUrl", "location", "country", "postingDate", "datePosted"}
    extra = {k: raw[k] for k in raw if k not in known}
    return {
        "provider": raw.get("provider", "unknown"),
        "url": raw["url"].strip(),
        "apply_url": raw.get("applyUrl") or raw.get("apply_url"),
        "posted_company_name": raw.get("company", ""),
        "title": raw.get("title", ""),
        "description": raw.get("description", ""),
        "location": raw.get("location", ""),
        "country": raw.get("country", ""),
        "remote_scope": _detect_remote_scope(
            raw.get("location", ""), raw.get("description", "")
        ),
        "date_posted": raw.get("postingDate") or raw.get("datePosted") or raw.get("postedRelative") or "",
        "source_payload": extra,
    }


def ingest_run_file(db_path: str, run_file: str) -> dict:
    result = {"inserted": 0, "updated": 0, "skipped": 0, "failed": 0, "error": None}
    con = get_connection(db_path)
    run_id = create_pipeline_run(con, f"ingest:{Path(run_file).name}")
    con.commit()

    try:
        with open(run_file) as f:
            raw_jobs = json.load(f)
    except Exception as e:
        result["failed"] = 1
        result["error"] = str(e)
        finish_pipeline_run(con, run_id, "failed", error=str(e),
                            summary_json=json.dumps(result))
        con.commit()
        con.close()
        return result

    if not isinstance(raw_jobs, list):
        result["failed"] = 1
        result["error"] = "Top-level JSON must be an array"
        finish_pipeline_run(con, run_id, "failed", error=result["error"],
                            summary_json=json.dumps(result))
        con.commit()
        con.close()
        return result

    for raw in raw_jobs:
        try:
            n = normalize_job(raw)
            if not n["url"]:
                result["skipped"] += 1
                continue
            domain = _extract_domain(raw.get("applyUrl"))
            company_id = upsert_company(con, n["posted_company_name"], domain)
            existing = get_job_by_url(con, n["url"])
            if existing is None:
                job_id = insert_job(
                    con,
                    url=n["url"],
                    provider=n["provider"],
                    company_id=company_id,
                    posted_company_name=n["posted_company_name"],
                    title=n["title"],
                    description=n["description"],
                    apply_url=n["apply_url"],
                    location=n["location"],
                    country=n["country"],
                    remote_scope=n["remote_scope"],
                    date_posted=n["date_posted"],
                    source_payload_json=json.dumps(n["source_payload"]),
                    status="new",
                )
                log_event(con, "job", job_id, "job_inserted", "ingest",
                          json.dumps({"provider": n["provider"], "url": n["url"]}))
                result["inserted"] += 1
            else:
                job_id = existing["id"]
                # Merge new source_payload into existing, preserving light_* tags
                existing_payload: dict = {}
                if existing["source_payload_json"]:
                    try:
                        existing_payload = json.loads(existing["source_payload_json"])
                    except Exception:
                        pass
                existing_payload.update(n["source_payload"])

                set_parts = [
                    "last_seen = datetime('now')",
                    "source_payload_json = ?",
                    "updated_at = datetime('now')",
                ]
                params: list = [json.dumps(existing_payload)]
                if not existing["apply_url"] and n["apply_url"]:
                    set_parts.append("apply_url = ?")
                    params.append(n["apply_url"])
                if not existing["description"] and n["description"]:
                    set_parts.append("description = ?")
                    params.append(n["description"])
                params.append(job_id)
                con.execute(
                    f"UPDATE jobs SET {', '.join(set_parts)} WHERE id = ?",
                    params
                )
                log_event(con, "job", job_id, "job_seen_again", "ingest",
                          json.dumps({"provider": n["provider"]}))
                result["updated"] += 1
        except Exception as e:
            result["failed"] += 1
            continue

    status = "succeeded" if result["failed"] == 0 else (
        "partial" if result["inserted"] + result["updated"] > 0 else "failed"
    )
    finish_pipeline_run(con, run_id, status, summary_json=json.dumps(result))
    con.commit()
    con.close()
    return result


def find_latest_run_files() -> list[Path]:
    files = []
    if not PROVIDERS_DIR.exists():
        return files
    for provider_dir in PROVIDERS_DIR.iterdir():
        if not provider_dir.is_dir():
            continue
        runs_dir = provider_dir / "runs"
        if not runs_dir.is_dir():
            continue
        json_files = sorted(runs_dir.glob("*_jobs_live_*.json"), reverse=True)
        if json_files:
            files.append(json_files[0])
    return files


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", required=True)
    parser.add_argument("--run-file")
    parser.add_argument("--all-latest", action="store_true")
    args = parser.parse_args()

    if not Path(args.db).exists():
        create_db(args.db)

    if args.run_file:
        result = ingest_run_file(args.db, args.run_file)
        print(json.dumps(result, indent=2))
    elif args.all_latest:
        files = find_latest_run_files()
        if not files:
            print("No run files found")
            sys.exit(0)
        totals = {"inserted": 0, "updated": 0, "skipped": 0, "failed": 0}
        for f in files:
            r = ingest_run_file(args.db, str(f))
            print(f"{f.name}: inserted={r['inserted']} updated={r['updated']} failed={r['failed']}")
            for k in totals:
                totals[k] += r[k]
        print(f"Total: {json.dumps(totals)}")
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
