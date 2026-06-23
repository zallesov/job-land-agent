from __future__ import annotations
import sys
from pathlib import Path
from .types import ShallowJob

_PROJECT_ROOT = Path(__file__).parent.parent.parent

sys.path.insert(0, str(_PROJECT_ROOT))


def dedup_jobs(jobs: list[ShallowJob]) -> list[ShallowJob]:
    if not jobs:
        return []

    from scripts.pb_client import get_pb
    pb = get_pb()

    dedup_keys = [j.dedup_key for j in jobs if j.dedup_key]
    existing_dedup_keys = pb.get_dedup_keys(dedup_keys) if dedup_keys else set()

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
