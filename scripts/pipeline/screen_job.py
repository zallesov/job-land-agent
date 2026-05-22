from __future__ import annotations
from pathlib import Path

from .hermes import hermes_call, CV_PATH
from .types import HermesResult
from scripts.db import get_connection, update_job_status

_DEFAULT_DB = str(Path(__file__).parent.parent.parent / "jobs.db")


def screen_job(job_id: int, db_path: str = _DEFAULT_DB) -> HermesResult:
    con = get_connection(db_path)
    try:
        result = hermes_call(
            "screen-job",
            {"job_id": job_id, "cv_path": str(CV_PATH)},
        )
        if result.success:
            data = result.data
            _upsert_assessment(con, job_id, data)
            update_job_status(con, job_id, "screened")
            con.commit()
        else:
            update_job_status(con, job_id, "screen_failed", comment=result.error)
            con.commit()
    finally:
        con.close()
    return result


def _upsert_assessment(con, job_id: int, data: dict) -> None:
    existing = con.execute(
        "SELECT id FROM job_assessments WHERE job_id = ?", (job_id,)
    ).fetchone()
    fields = (
        data.get("apply_verdict"),
        data.get("relevance_score"),
        data.get("one_line_summary"),
        data.get("seniority_fit"),
        data.get("tech_stack_fit"),
        data.get("remote_eligibility"),
        data.get("salary_assessment"),
    )
    if existing:
        con.execute("""
            UPDATE job_assessments SET
                assessed_at = datetime('now'),
                assessment_status = 'screened',
                apply_verdict = ?, relevance_score = ?,
                one_line_summary = ?, seniority_fit = ?,
                tech_stack_fit = ?, remote_eligibility = ?,
                salary_assessment = ?,
                updated_at = datetime('now')
            WHERE job_id = ?
        """, fields + (job_id,))
    else:
        con.execute("""
            INSERT INTO job_assessments (
                job_id, assessed_at, assessment_status,
                apply_verdict, relevance_score, one_line_summary,
                seniority_fit, tech_stack_fit, remote_eligibility, salary_assessment
            ) VALUES (?, datetime('now'), 'screened', ?, ?, ?, ?, ?, ?, ?)
        """, (job_id,) + fields)
