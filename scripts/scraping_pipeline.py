#!/usr/bin/env python3
"""
Scraping pipeline orchestrator.

Each provider script reads config/user.yaml itself and handles all location
and search-term loops internally. The pipeline calls each provider once.

Usage:
  python3 scripts/scraping_pipeline.py --provider greenhouse
  python3 scripts/scraping_pipeline.py --provider jobleads --titles "Software Engineer,AI Engineer"

Options:
  --provider <name>   Provider: greenhouse | jobleads | wellfound | sprout
  --titles <str>      Comma-separated title search terms (optional; overrides config)
  --cdp-url <url>     CDP endpoint (default: http://localhost:9222)
  --db <path>         DB path (default: jobs.db in project root)
"""
from __future__ import annotations

import argparse
import importlib
import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.pipeline.dedup import dedup_jobs
from scripts.pipeline.ingest import ingest_jobs
from scripts.pipeline.enrich_job import enrich_job
from scripts.pipeline.sanity_check_job import sanity_check_job
from scripts.pipeline.notify import send_daily_digest

PROJECT_ROOT = Path(__file__).parent.parent
DEFAULT_DB = str(PROJECT_ROOT / "jobs.db")
DEFAULT_CDP = "http://localhost:9222"
PROVIDERS = {"greenhouse", "jobleads", "wellfound", "sprout"}


def _queue_research(job_ids: list[int], db_path: str) -> int:
    """Create pending research_job commands for each job that doesn't have one yet."""
    if not job_ids:
        return 0
    queued = 0
    con = sqlite3.connect(db_path)
    try:
        for job_id in job_ids:
            existing = con.execute(
                "SELECT id FROM agent_commands "
                "WHERE command_type='research_job' AND status IN ('pending','running') "
                "AND json_extract(payload_json,'$.job_id')=?",
                (job_id,),
            ).fetchone()
            if existing:
                continue
            con.execute(
                "INSERT INTO agent_commands (command_type, payload_json, status, created_by) "
                "VALUES ('research_job', ?, 'pending', 'pipeline')",
                (json.dumps({"job_id": job_id}),),
            )
            queued += 1
        con.commit()
    finally:
        con.close()
    return queued


def run(
    provider: str,
    cdp_url: str = DEFAULT_CDP,
    db_path: str = DEFAULT_DB,
    titles: list[str] | None = None,
    _check_auth=None,
    _scrape_jobs=None,
) -> None:
    if _check_auth is None:
        _check_auth = importlib.import_module(f"scripts.providers.{provider}.check_auth").check_auth
    if _scrape_jobs is None:
        _scrape_jobs = importlib.import_module(f"scripts.providers.{provider}.scrape_jobs").scrape_jobs

    _check_auth(cdp_url)

    try:
        raw_jobs = _scrape_jobs(cdp_url, titles=titles, db_path=db_path)
    except Exception as e:
        from scripts.telegram_notify import pipeline_failure
        pipeline_failure(provider, "scrape", str(e), "")
        raise

    print(f"[pipeline] {provider}: scraped {len(raw_jobs)} jobs", flush=True)

    new_jobs = dedup_jobs(raw_jobs, db_path=db_path)
    print(f"[pipeline] {len(new_jobs)} new after dedup", flush=True)

    job_ids = ingest_jobs(new_jobs, db_path=db_path)
    print(f"[pipeline] ingested {len(job_ids)} jobs", flush=True)

    enrich_failures: list[tuple[int, str]] = []
    enriched_ids: list[int] = []
    for job_id in job_ids:
        result = enrich_job(job_id, db_path=db_path)
        if result.success:
            enriched_ids.append(job_id)
        else:
            enrich_failures.append((job_id, result.error or "unknown"))

    sanity_failures: list[tuple[int, str]] = []
    for job_id in enriched_ids:
        result = sanity_check_job(job_id, db_path=db_path)
        if not result.success:
            sanity_failures.append((job_id, result.error or "unknown"))

    send_daily_digest(enrich_failures=enrich_failures, sanity_failures=sanity_failures)

    queued = _queue_research(job_ids, db_path=db_path)
    print(
        f"[pipeline] done. enrich_failures={len(enrich_failures)} "
        f"sanity_failures={len(sanity_failures)} research_queued={queued}",
        flush=True,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", required=True, choices=PROVIDERS)
    parser.add_argument("--titles", default=None,
                        help="Comma-separated job title search terms")
    parser.add_argument("--cdp-url", default=DEFAULT_CDP)
    parser.add_argument("--db", default=DEFAULT_DB)
    args = parser.parse_args()

    titles = [t.strip() for t in args.titles.split(",")] if args.titles else None

    run(
        provider=args.provider,
        cdp_url=args.cdp_url,
        db_path=args.db,
        titles=titles,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
