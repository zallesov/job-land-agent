#!/usr/bin/env python3
"""
Scraping pipeline orchestrator.

Usage:
  python3 scripts/scraping_pipeline.py --provider greenhouse --location Berlin
  python3 scripts/scraping_pipeline.py --provider jobleads --location Barcelona \
    --titles "Software Engineer,AI Engineer"

Options:
  --provider <name>   Provider: greenhouse | jobleads | wellfound | sprout
  --location <city>   City name — must match a location entry in config/user.yaml
  --titles <str>      Comma-separated job title search terms (optional)
  --cdp-url <url>     CDP endpoint (default: http://localhost:9222)
  --db <path>         DB path (default: jobs.db in project root)
"""
from __future__ import annotations

import argparse
import importlib
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


def run(
    provider: str,
    location: dict,
    titles: list[str] | None = None,
    cdp_url: str = DEFAULT_CDP,
    db_path: str = DEFAULT_DB,
    _check_auth=None,
    _scrape_jobs=None,
) -> None:
    if _check_auth is None:
        _check_auth = importlib.import_module(f"scripts.providers.{provider}.check_auth").check_auth
    if _scrape_jobs is None:
        _scrape_jobs = importlib.import_module(f"scripts.providers.{provider}.scrape_jobs").scrape_jobs
    check_auth_fn = _check_auth
    scrape_jobs_fn = _scrape_jobs

    check_auth_fn(cdp_url)

    try:
        raw_jobs = scrape_jobs_fn(location, cdp_url, titles=titles)
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
    print(
        f"[pipeline] done. enrich_failures={len(enrich_failures)} "
        f"sanity_failures={len(sanity_failures)}",
        flush=True,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", required=True, choices=PROVIDERS)
    parser.add_argument("--location", required=True,
                        help="City name matching a location entry in config/user.yaml")
    parser.add_argument("--titles", default=None,
                        help="Comma-separated job title search terms")
    parser.add_argument("--cdp-url", default=DEFAULT_CDP)
    parser.add_argument("--db", default=DEFAULT_DB)
    args = parser.parse_args()

    import yaml
    config_path = PROJECT_ROOT / "config" / "user.yaml"
    if not config_path.exists():
        print(
            f"ERROR: {config_path} not found. "
            "Copy config/user.yaml.example to config/user.yaml and fill it in.",
            file=sys.stderr,
        )
        return 1
    config = yaml.safe_load(config_path.read_text())
    location_dict = next(
        (loc for loc in config.get("locations", [])
         if loc["city"].lower() == args.location.lower()),
        None,
    )
    if location_dict is None:
        available = [loc["city"] for loc in config.get("locations", [])]
        print(
            f"ERROR: Location {args.location!r} not found in config/user.yaml. "
            f"Available: {available}",
            file=sys.stderr,
        )
        return 1

    titles = [t.strip() for t in args.titles.split(",")] if args.titles else None

    run(
        provider=args.provider,
        location=location_dict,
        titles=titles,
        cdp_url=args.cdp_url,
        db_path=args.db,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
