from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

from scripts.pipeline.types import ShallowJob

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
CSV_PATH = PROJECT_ROOT / "tmp" / "filtered_dev.csv"


def scrape_jobs(cdp_url: str, titles: list[str] | None = None, db_path: str | None = None) -> list[ShallowJob]:
    """Read jobs from a pre-filtered CSV file instead of scraping a live provider."""
    if not CSV_PATH.exists():
        print(f"[csvfeed] CSV not found: {CSV_PATH}", file=sys.stderr, flush=True)
        return []

    jobs: list[ShallowJob] = []
    with open(CSV_PATH, "r", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            title = (row.get("Title") or "").strip()
            if not title:
                continue

            company = (row.get("Company Name") or "").strip()
            url = (row.get("Apply Url") or "").strip()
            location = (row.get("Country") or "").strip()
            salary_raw = _build_salary(row)
            date_posted = _parse_date(row.get("Date Posted") or "")

            jobs.append(
                ShallowJob(
                    provider="csvfeed",
                    title=title,
                    company=company,
                    url=url,
                    location=location,
                    country=_clean_country(location),
                    dedup_key=f"{company}::{title}",
                    posting_date=date_posted,
                    salary_raw=salary_raw,
                    status="new",
                )
            )

    print(f"[csvfeed] read {len(jobs)} jobs from {CSV_PATH.name}", flush=True)
    return jobs


def _build_salary(row: dict) -> str | None:
    min_s = (row.get("Salary Min") or "").strip()
    max_s = (row.get("Salary Max") or "").strip()
    currency = (row.get("Compensation Currency") or "").strip()
    if min_s or max_s:
        parts = []
        if min_s:
            parts.append(min_s)
        if max_s:
            parts.append(max_s)
        result = "-".join(parts)
        if currency:
            result += f" {currency}"
        return result
    return None


def _parse_date(raw: str) -> str | None:
    if not raw:
        return None
    raw = raw.strip()
    if "ago" in raw:
        return None
    if raw.count("-") == 2:
        return raw
    return None


def _clean_country(country: str) -> str | None:
    if not country:
        return None
    clean = re.sub(r"[^\x20-\x7E]", "", country).strip()
    return clean or None
