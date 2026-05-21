from __future__ import annotations
import sqlite3
from pathlib import Path

from .types import ShallowJob

_DEFAULT_DB = str(Path(__file__).parent.parent.parent / "jobs.db")


_SKIP_COMMENT = "Auto-filtered by job_filter before research"


def ingest_jobs(jobs: list[ShallowJob], db_path: str = _DEFAULT_DB) -> list[int]:
    """Insert jobs. Returns IDs of non-skip jobs only (skip jobs saved but not enriched)."""
    if not jobs:
        return []
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    ids: list[int] = []
    try:
        for j in jobs:
            is_skip = j.status == "skip"
            cur = con.execute(
                """INSERT INTO jobs
                   (url, apply_url, provider, posted_company_name, title, location, country,
                    date_posted, salary_range, dedup_key, status, comment)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (j.url, j.url, j.provider, j.company, j.title, j.location, j.country,
                 j.posting_date, j.salary_raw, j.dedup_key, j.status,
                 _SKIP_COMMENT if is_skip else None),
            )
            if not is_skip:
                ids.append(cur.lastrowid)
        con.commit()
    finally:
        con.close()
    return ids
