#!/usr/bin/env python3
"""
Batch enrich jobs by ID list — loops over each ID and calls enrich_job.

Usage:
  python3 scripts/enrich_jobs_batch.py --job-ids 42,43,44
  python3 scripts/enrich_jobs_batch.py --job-ids 42 43 44
  python3 scripts/enrich_jobs_batch.py --cdp-url http://localhost:9222 --job-ids 42,43
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.pipeline.enrich_jobs_batch import enrich_jobs_batch

PROJECT_ROOT = Path(__file__).parent.parent
DEFAULT_CDP = "http://localhost:9222"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--job-ids", required=True, nargs="+",
                        help="Job IDs — space-separated or a single comma-separated value")
    parser.add_argument("--cdp-url", default=DEFAULT_CDP)
    parser.add_argument("--workers", type=int, default=5,
                        help="Max parallel browser tabs (default: 5)")
    args = parser.parse_args()

    raw = " ".join(args.job_ids)
    job_ids = [int(x.strip()) for x in raw.replace(",", " ").split() if x.strip()]

    print(f"Enriching {len(job_ids)} jobs with up to {args.workers} parallel tabs…", flush=True)
    ok_ids, failures = enrich_jobs_batch(job_ids, cdp_url=args.cdp_url, max_workers=args.workers)

    print(f"\nDone: {len(ok_ids)} ok, {len(failures)} failed")
    if failures:
        for job_id, err in failures:
            print(f"  FAIL {job_id}: {err}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
