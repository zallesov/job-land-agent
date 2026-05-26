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
    finally:
        con.close()

    # Dedup within the batch itself (two scraped jobs may share a key).
    seen_keys: set[str] = set()
    seen_urls: set[str] = set()
    deduped: list[ShallowJob] = []
    for j in jobs:
        if j.dedup_key:
            if j.dedup_key in seen_keys or j.dedup_key in existing_dedup_keys:
                continue
            seen_keys.add(j.dedup_key)
            deduped.append(j)
            continue
        if j.url:
            if j.url in seen_urls:
                continue
            seen_urls.add(j.url)
        deduped.append(j)

    return deduped
