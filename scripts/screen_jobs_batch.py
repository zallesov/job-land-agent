#!/usr/bin/env python3
"""
Batch screen jobs by ID list — runs up to 5 parallel DeepSeek calls.

Usage:
  python3 scripts/batch_screen_jobs.py --job-ids 42,43,44
  python3 scripts/batch_screen_jobs.py --job-ids 42 43 44
  python3 scripts/batch_screen_jobs.py --db jobs.db --workers 3 --job-ids 42,43
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.pipeline.screen_jobs_batch import screen_jobs_batch

PROJECT_ROOT = Path(__file__).parent.parent
DEFAULT_DB = str(PROJECT_ROOT / "jobs.db")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--job-ids", required=True, nargs="+",
                        help="Job IDs — space-separated or a single comma-separated value")
    parser.add_argument("--db", default=DEFAULT_DB)
    parser.add_argument("--workers", type=int, default=5,
                        help="Max parallel screening workers (default: 5)")
    args = parser.parse_args()

    raw = " ".join(args.job_ids)
    job_ids = [int(x.strip()) for x in raw.replace(",", " ").split() if x.strip()]

    print(f"Screening {len(job_ids)} jobs with up to {args.workers} workers...", flush=True)
    ok_ids, failures = screen_jobs_batch(job_ids, db_path=args.db, max_workers=args.workers)

    print(f"\nDone: {len(ok_ids)} ok, {len(failures)} failed")
    if failures:
        for job_id, err in failures:
            print(f"  FAIL {job_id}: {err}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
