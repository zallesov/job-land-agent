from __future__ import annotations

import sys
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit

from playwright.sync_api import sync_playwright

from scripts.pipeline.types import ShallowJob
from scripts.providers._shared.job_filter import is_relevant

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
HIRIFY_BASE = "https://hirify.me"


def _load_config() -> dict:
    try:
        import yaml  # noqa: PLC0415
        p = PROJECT_ROOT / "config" / "user.yaml"
        return yaml.safe_load(p.read_text()) or {} if p.exists() else {}
    except Exception:
        return {}


def _canonical_url(url: str) -> str:
    absolute = urljoin(HIRIFY_BASE, (url or "").strip())
    parts = urlsplit(absolute)
    return urlunsplit((parts.scheme, parts.netloc, parts.path.rstrip("/"), "", ""))


def _normalize_raw_job(raw: dict) -> ShallowJob:
    title = (raw.get("title") or "").strip()
    company = (raw.get("company") or "").strip() or "Company hidden"
    url = _canonical_url(raw.get("url") or "")
    relevant = is_relevant({"title": title})
    return ShallowJob(
        provider="hirify",
        title=title,
        company=company,
        url=url,
        location=(raw.get("location") or "").strip(),
        country=(raw.get("country") or None),
        dedup_key=f"{company}::{title}",
        posting_date=None,
        salary_raw=(raw.get("salaryRaw") or None),
        status="listed" if relevant else "skip",
    )
