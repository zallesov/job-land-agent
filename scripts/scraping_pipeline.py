#!/usr/bin/env python3
"""
Scraping pipeline orchestrator.

Usage:
  python3 scripts/scraping_pipeline.py --provider greenhouse --location berlin
  python3 scripts/scraping_pipeline.py --provider jobleads --location spain
  python3 scripts/scraping_pipeline.py --provider wellfound --location berlin
  python3 scripts/scraping_pipeline.py --provider sprout --location berlin

Options:
  --provider <name>   Provider: greenhouse | jobleads | wellfound | sprout
  --location <name>   Location preset: berlin | spain
  --cdp-url <url>     CDP endpoint (default: http://localhost:9222)
  --db <path>         DB path (default: jobs.db in project root)
"""
from __future__ import annotations

import argparse
import importlib
from pathlib import Path

from scripts.pipeline.dedup import dedup_jobs
from scripts.pipeline.ingest import ingest_jobs
from scripts.pipeline.enrich_job import enrich_job
from scripts.pipeline.sanity_check_job import sanity_check_job
from scripts.pipeline.notify import send_daily_digest
from scripts.db import get_connection

PROJECT_ROOT = Path(__file__).parent.parent
DEFAULT_DB = str(PROJECT_ROOT / "jobs.db")
DEFAULT_CDP = "http://localhost:9222"
PROVIDERS = {"greenhouse", "jobleads", "wellfound", "sprout"}


def run(
    provider: str,
    location: str,
    cdp_url: str = DEFAULT_CDP,
    db_path: str = DEFAULT_DB,
    _check_auth=None,
    _scrape_jobs=None,
) -> None:
    auth_mod = importlib.import_module(f"scripts.providers.{provider}.check_auth")
    scrape_mod = importlib.import_module(f"scripts.providers.{provider}.scrape_jobs")
    check_auth_fn = _check_auth or auth_mod.check_auth
    scrape_jobs_fn = _scrape_jobs or scrape_mod.scrape_jobs

    check_auth_fn(cdp_url)

    try:
        raw_jobs = scrape_jobs_fn(location, cdp_url)
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
    for job_id in job_ids:
        result = enrich_job(job_id, db_path=db_path)
        if not result.success:
            enrich_failures.append((job_id, result.error or "unknown"))

    con = get_connection(db_path)
    enriched_ids = []
    for jid in job_ids:
        row = con.execute("SELECT status FROM jobs WHERE id = ?", (jid,)).fetchone()
        if row and row["status"] == "new":
            enriched_ids.append(jid)
    con.close()

    sanity_failures: list[tuple[int, str]] = []
    for job_id in enriched_ids:
        result = sanity_check_job(job_id, db_path=db_path)
        if not result.success:
            sanity_failures.append((job_id, result.error or "unknown"))

    send_daily_digest(enrich_failures=enrich_failures, sanity_failures=sanity_failures)
    print(
        f"[pipeline] done. enrich_failures={len(enrich_failures)} "
        f"sanity_failures={len(sanity_failures)}",
        flush=True,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", required=True, choices=PROVIDERS)
    parser.add_argument("--location", required=True)
    parser.add_argument("--cdp-url", default=DEFAULT_CDP)
    parser.add_argument("--db", default=DEFAULT_DB)
    args = parser.parse_args()
    run(
        provider=args.provider,
        location=args.location,
        cdp_url=args.cdp_url,
        db_path=args.db,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
