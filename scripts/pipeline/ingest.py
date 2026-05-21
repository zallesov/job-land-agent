from __future__ import annotations
import sqlite3
from pathlib import Path

from .types import ShallowJob

_DEFAULT_DB = str(Path(__file__).parent.parent.parent / "jobs.db")


def ingest_jobs(jobs: list[ShallowJob], db_path: str = _DEFAULT_DB) -> list[int]:
    if not jobs:
        return []
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    ids: list[int] = []
    try:
        for j in jobs:
            cur = con.execute(
                """INSERT INTO jobs
                   (url, provider, posted_company_name, title, location, country,
                    date_posted, salary_range, dedup_key, status)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'listed')""",
                (j.url, j.provider, j.company, j.title, j.location, j.country,
                 j.posting_date, j.salary_raw, j.dedup_key),
            )
            ids.append(cur.lastrowid)
        con.commit()
    finally:
        con.close()
    return ids
