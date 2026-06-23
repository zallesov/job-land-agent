from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from .screen_job import screen_job
from .types import HermesResult


def screen_jobs_batch(
    job_ids: list[int],
    max_workers: int = 5,
) -> tuple[list[int], list[tuple[int, str]]]:
    """Screen a list of jobs in parallel. Returns (ok_ids, failures)."""
    ok_ids: list[int] = []
    failures: list[tuple[int, str]] = []

    futures = {}
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        for job_id in job_ids:
            fut = pool.submit(screen_job, job_id)
            futures[fut] = job_id

        total = len(futures)
        done = 0
        for fut in as_completed(futures):
            job_id = futures[fut]
            done += 1
            try:
                result: HermesResult = fut.result()
            except Exception as e:
                result = HermesResult(success=False, data={}, error=str(e), raw_output="")

            if result.success:
                print(f"[screen] {done}/{total} OK    job_id={job_id}", flush=True)
                ok_ids.append(job_id)
            else:
                print(f"[screen] {done}/{total} FAIL  job_id={job_id}  error={result.error}", flush=True)
                failures.append((job_id, result.error or "unknown"))

    return ok_ids, failures
