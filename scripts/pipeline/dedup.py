from __future__ import annotations
import sqlite3
from pathlib import Path

from .types import ShallowJob

_PROJECT_ROOT = Path(__file__).parent.parent.parent
_DEFAULT_DB = str(_PROJECT_ROOT / "jobs.db")


def dedup_jobs(jobs: list[ShallowJob], db_path: str = _DEFAULT_DB) -> list[ShallowJob]:
    if not jobs:
        return []
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    try:
        dedup_keys = [j.dedup_key for j in jobs if j.dedup_key]
        urls = [j.url for j in jobs if j.url]

        existing_dedup_keys: set[str] = set()
        if dedup_keys:
            placeholders = ",".join("?" * len(dedup_keys))
            existing_dedup_keys = {
                row[0]
                for row in con.execute(
                    f"SELECT dedup_key FROM jobs WHERE dedup_key IN ({placeholders})",
                    dedup_keys,
                ).fetchall()
            }

        existing_urls: set[str] = set()
        if urls:
            placeholders = ",".join("?" * len(urls))
            existing_urls = {
                row[0]
                for row in con.execute(
                    f"SELECT url FROM jobs WHERE url IN ({placeholders})", urls
                ).fetchall()
            }
    finally:
        con.close()
    return [
        j
        for j in jobs
        if j.dedup_key not in existing_dedup_keys and j.url not in existing_urls
    ]
