#!/usr/bin/env python3
"""
Add a single job by URL — runs the full pipeline inline.

Steps: dedup → ingest → enrich (CDP) → screen (Hermes) → telegram notify

Usage:
  python3 scripts/add_job_by_url.py --url https://wellfound.com/jobs/123-title
  python3 scripts/add_job_by_url.py --url <url> --cdp-url http://localhost:9222
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.pipeline.dedup import dedup_jobs
from scripts.pipeline.ingest import ingest_jobs
from scripts.pipeline.enrich_job import enrich_job
from scripts.pipeline.screen_job import screen_job
from scripts.pipeline.types import ShallowJob

DEFAULT_CDP = "http://localhost:9222"


def _notify(message: str) -> None:
    import subprocess
    try:
        result = subprocess.run(
            ["hermes", "send", "--to", "telegram", message],
            capture_output=True, timeout=10,
        )
        if result.returncode != 0:
            print(f"[telegram] send failed: {result.stderr.decode()[:200]}", flush=True)
    except FileNotFoundError:
        print("[telegram] hermes not found in PATH — skipping notification", flush=True)
    except Exception as e:
        print(f"[telegram] {e}", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--cdp-url", default=DEFAULT_CDP)
    args = parser.parse_args()

    url = args.url.strip()

    job = ShallowJob(
        provider="manual",
        title="",
        company="",
        url=url,
        location="",
        country=None,
        dedup_key=url,
        posting_date=None,
        salary_raw=None,
        status="new",
    )

    new = dedup_jobs([job])
    if not new:
        print(f"DUPLICATE: {url} already in DB")
        return 0

    ids = ingest_jobs(new)
    job_id = ids[0]
    print(f"Ingested job_id={job_id}", flush=True)

    result = enrich_job(job_id, cdp_url=args.cdp_url)
    if not result.success:
        print(f"ENRICH_FAILED: {result.error}")
        _notify(f"❌ add-job failed (enrich)\n{url}\n{result.error}")
        return 1
    print(f"Enriched: {result.data.get('title', '')[:80]}", flush=True)

    result = screen_job(job_id)
    if not result.success:
        print(f"SCREEN_FAILED: {result.error}")
        _notify(f"⚠️ add-job screened failed\n{url}\n{result.error}")
        return 1
    print("Screened", flush=True)

    from scripts.pb_client import get_pb
    pb = get_pb()
    j = pb.get_job(job_id) or {}
    a = pb.get_one('job_assessments', f"job_id='{str(job_id).zfill(15)}'") or {}

    title = j.get("title") or url
    company = j.get("posted_company_name") or "?"
    verdict = a.get("apply_verdict") or "?"
    score = a.get("relevance_score") or "?"
    summary = a.get("one_line_summary") or "?"

    print(f"\nDone — job #{job_id}")
    print(f"  {title} @ {company}")
    print(f"  Verdict: {verdict}  (R:{score})")
    print(f"  {summary}")

    _notify(
        f"📋 Job added #{job_id}\n"
        f"{title} @ {company}\n"
        f"Verdict: {verdict}  R:{score}\n"
        f"{summary}\n"
        f"Dashboard: http://localhost:3000"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
