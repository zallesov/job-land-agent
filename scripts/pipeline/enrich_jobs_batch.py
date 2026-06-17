from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from .enrich_job import enrich_job
from .types import HermesResult

_DEFAULT_CDP = "http://localhost:9222"


def enrich_jobs_batch(
    job_ids: list[int],
    cdp_url: str = _DEFAULT_CDP,
    max_workers: int = 5,
) -> tuple[list[int], list[tuple[int, str]]]:
    """Enrich a list of jobs in parallel browser tabs. Returns (ok_ids, failures)."""
    ok_ids: list[int] = []
    failures: list[tuple[int, str]] = []

    futures = {}
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        for job_id in job_ids:
            fut = pool.submit(enrich_job, job_id, cdp_url)
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
                title = (result.data.get("title") or "")[:60]
                print(f"[enrich] {done}/{total} OK    job_id={job_id}  {title}", flush=True)
                ok_ids.append(job_id)
            else:
                print(f"[enrich] {done}/{total} FAIL  job_id={job_id}  error={result.error}", flush=True)
                failures.append((job_id, result.error or "unknown"))

    return ok_ids, failures
