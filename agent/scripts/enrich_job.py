#!/usr/bin/env python3
"""
Enrich a single job by ID — navigates to the job URL in the existing Chrome
session (CDP) and extracts title, description, apply_url, salary, date_posted.

Usage:
  python3 scripts/enrich_job.py --job-id 42
  python3 scripts/enrich_job.py --job-id 42 --cdp-url http://localhost:9222
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.pipeline.enrich_job import enrich_job

PROJECT_ROOT = Path(__file__).parent.parent
DEFAULT_CDP = "http://localhost:9222"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--job-id", required=True, type=int)
    parser.add_argument("--cdp-url", default=DEFAULT_CDP)
    args = parser.parse_args()

    result = enrich_job(args.job_id, cdp_url=args.cdp_url)
    if result.success:
        print(f"OK  job_id={args.job_id}  title={result.data.get('title', '')[:80]}")
        return 0
    else:
        print(f"FAIL  job_id={args.job_id}  error={result.error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
