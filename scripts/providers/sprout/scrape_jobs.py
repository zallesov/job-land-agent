from __future__ import annotations
from playwright.sync_api import sync_playwright

from scripts.pipeline.types import ShallowJob
from scripts.providers._shared.job_filter import is_relevant
from scripts.scrape_sprout import LOCATION_PRESETS, SPROUT_BASE, collect_sprout

DEFAULT_TITLES = [
    "Software Engineer", "Backend Engineer", "AI Engineer",
    "Platform Engineer", "Engineering Manager",
]


def scrape_jobs(location: str, cdp_url: str) -> list[ShallowJob]:
    preset_key = location.lower()
    if preset_key not in LOCATION_PRESETS:
        raise ValueError(f"Unknown location: {location!r}")
    country_name = {"berlin": "Germany", "spain": "Spain"}.get(preset_key, location)

    raw_rows: list[dict] = []
    with sync_playwright() as pw:
        browser = pw.chromium.connect_over_cdp(cdp_url)
        ctx = browser.contexts[0]
        page = ctx.new_page()
        try:
            page.goto(f"{SPROUT_BASE}/jobs", wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(2000)
            raw_rows = collect_sprout(
                page,
                titles=DEFAULT_TITLES,
                location=LOCATION_PRESETS[preset_key],
                country=country_name,
            )
        finally:
            browser.close()

    jobs: list[ShallowJob] = []
    for r in raw_rows:
        if not r.get("title") or not r.get("company"):
            continue
        j = ShallowJob(
            provider="sprout",
            title=r["title"],
            company=r["company"],
            url=r["url"],
            location=r.get("location", ""),
            country=r.get("country") or country_name,
            dedup_key=f"{r['company']}::{r['title']}",
            posting_date=None,
            salary_raw=r.get("salary") or None,
        )
        if is_relevant({"title": j.title}):
            jobs.append(j)
    return jobs
