from __future__ import annotations
import sqlite3
from pathlib import Path

from .hermes import hermes_call, CV_PATH
from .types import HermesResult
from scripts.db import get_connection, update_job_status

_DEFAULT_DB = str(Path(__file__).parent.parent.parent / "jobs.db")


def enrich_job(job_id: int, db_path: str = _DEFAULT_DB) -> HermesResult:
    con = get_connection(db_path)
    try:
        job = con.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        if job is None:
            return HermesResult(
                success=False, data={}, error=f"job {job_id} not found", raw_output=""
            )
        result = hermes_call(
            "enrich-job",
            {"job_id": job_id, "url": job["url"], "cv_path": str(CV_PATH)},
        )
        if result.success:
            d = result.data
            con.execute(
                """UPDATE jobs SET title = COALESCE(?, title),
                   description = ?, apply_url = ?, salary_range = COALESCE(?, salary_range),
                   date_posted = COALESCE(?, date_posted),
                   status = 'new', updated_at = datetime('now')
                   WHERE id = ?""",
                (d.get("title"), d.get("description"), d.get("apply_url"),
                 d.get("salary_range"), d.get("date_posted"), job_id),
            )
        else:
            update_job_status(con, job_id, "enrich_failed", comment=result.error)
        con.commit()
    finally:
        con.close()
    return result
