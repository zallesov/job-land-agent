from __future__ import annotations

from typing import Iterable

from .types import ShallowJob


def _existing_keys_urls(existing: Iterable[dict] | None) -> tuple[set[str], set[str]]:
    keys: set[str] = set()
    urls: set[str] = set()
    for rec in existing or []:
        k = rec.get("dedup_key")
        if k:
            keys.add(k)
        u = rec.get("url")
        if u:
            urls.add(u)
    return keys, urls


def dedup_jobs(scraped: list[ShallowJob], existing: Iterable[dict] | None = None) -> list[ShallowJob]:
    """Filter freshly scraped jobs against already-known jobs, purely locally.

    Two inputs, no network:
      - ``scraped``: jobs we just scraped this run (ShallowJob list).
      - ``existing``: jobs already in the database, fetched once via the MCP
        ``jobs_list`` tool and passed in as plain dicts.

    A scraped job is dropped if its ``dedup_key`` (or ``url`` when it has no
    key) already appears in ``existing`` or earlier in this same batch.
    """
    if not scraped:
        return []

    existing_keys, existing_urls = _existing_keys_urls(existing)

    seen_keys: set[str] = set()
    seen_urls: set[str] = set()
    deduped: list[ShallowJob] = []
    for j in scraped:
        if j.dedup_key:
            if j.dedup_key in seen_keys or j.dedup_key in existing_keys:
                continue
            seen_keys.add(j.dedup_key)
            deduped.append(j)
            continue
        if j.url:
            if j.url in seen_urls or j.url in existing_urls:
                continue
            seen_urls.add(j.url)
        deduped.append(j)

    return deduped
