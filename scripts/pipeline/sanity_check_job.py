from __future__ import annotations
from pathlib import Path

from .hermes import hermes_call, CV_PATH
from .types import HermesResult
from scripts.db import get_connection, update_job_status

_DEFAULT_DB = str(Path(__file__).parent.parent.parent / "jobs.db")


def sanity_check_job(job_id: int, db_path: str = _DEFAULT_DB) -> HermesResult:
    con = get_connection(db_path)
    try:
        result = hermes_call(
            "sanity-check-job",
            {"job_id": job_id, "cv_path": str(CV_PATH)},
        )
        if result.success:
            if result.data.get("verdict") == "skip":
                update_job_status(
                    con, job_id, "not_interested",
                    comment=result.data.get("reason"),
                )
                con.commit()
            # verdict=pass: no status change needed
        else:
            update_job_status(con, job_id, "sanity_failed", comment=result.error)
            con.commit()
    finally:
        con.close()
    return result
