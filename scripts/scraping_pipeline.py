#!/usr/bin/env python3
"""
Scraping pipeline orchestrator.

Each provider script reads config/user.yaml itself and handles all location
and search-term loops internally. The pipeline calls each provider once.

Usage:
  python3 scripts/scraping_pipeline.py --provider greenhouse
  python3 scripts/scraping_pipeline.py --provider jobleads --titles "Software Engineer,AI Engineer"

Options:
  --provider <name>   Provider: greenhouse | jobleads | wellfound | sprout | hirify
  --titles <str>      Comma-separated title search terms (optional; overrides config)
  --cdp-url <url>     CDP endpoint (default: http://localhost:9222)
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
from scripts.pipeline.screen_job import screen_job
from scripts.pipeline.notify import send_daily_digest

PROJECT_ROOT = Path(__file__).parent.parent
DEFAULT_CDP = "http://localhost:9222"
PROVIDERS = {"greenhouse", "jobleads", "wellfound", "sprout", "hirify", "csvfeed"}


def run(
    provider: str,
    cdp_url: str = DEFAULT_CDP,
    titles: list[str] | None = None,
    location: dict | None = None,
    _check_auth=None,
    _scrape_jobs=None,
) -> None:
    if _check_auth is None:
        _check_auth = importlib.import_module(f"scripts.providers.{provider}.check_auth").check_auth
    if _scrape_jobs is None:
        _scrape_jobs = importlib.import_module(f"scripts.providers.{provider}.scrape_jobs").scrape_jobs

    _check_auth(cdp_url)

    try:
        if location is not None:
            raw_jobs = _scrape_jobs(location, cdp_url, titles=titles)
        else:
            raw_jobs = _scrape_jobs(cdp_url, titles=titles)
    except Exception as e:
        from scripts.telegram_notify import pipeline_failure
        pipeline_failure(provider, "scrape", str(e), "")
        raise

    print(f"[pipeline] {provider}: scraped {len(raw_jobs)} jobs", flush=True)

    new_jobs = dedup_jobs(raw_jobs)
    print(f"[pipeline] {len(new_jobs)} new after dedup", flush=True)

    job_ids = ingest_jobs(new_jobs)
    print(f"[pipeline] ingested {len(job_ids)} jobs", flush=True)

    enrich_failures: list[tuple[int, str]] = []
    enriched_ids: list[int] = []
    for i, job_id in enumerate(job_ids, 1):
        print(f"[enrich] {i}/{len(job_ids)} job_id={job_id}", flush=True)
        result = enrich_job(job_id)
        if result.success:
            title = (result.data.get("title") or "")[:60]
            print(f"[enrich] OK  job_id={job_id}  title={title!r}", flush=True)
            enriched_ids.append(job_id)
        else:
            print(f"[enrich] FAIL  job_id={job_id}  error={result.error}", flush=True)
            enrich_failures.append((job_id, result.error or "unknown"))

    print(f"[screen] screening {len(enriched_ids)} jobs", flush=True)
    screen_failures: list[tuple[int, str]] = []
    for i, job_id in enumerate(enriched_ids, 1):
        print(f"[screen] {i}/{len(enriched_ids)} job_id={job_id}", flush=True)
        result = screen_job(job_id)
        if not result.success:
            screen_failures.append((job_id, result.error or "unknown"))

    send_daily_digest(enrich_failures=enrich_failures, screen_failures=screen_failures)

    print(
        f"[pipeline] done. enrich_failures={len(enrich_failures)} "
        f"screen_failures={len(screen_failures)}",
        flush=True,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", required=True, choices=PROVIDERS)
    parser.add_argument("--titles", default=None,
                        help="Comma-separated job title search terms")
    parser.add_argument("--cdp-url", default=DEFAULT_CDP)
    args = parser.parse_args()

    titles = [t.strip() for t in args.titles.split(",")] if args.titles else None

    run(
        provider=args.provider,
        cdp_url=args.cdp_url,
        titles=titles,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
