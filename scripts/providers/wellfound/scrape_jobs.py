from __future__ import annotations
from playwright.sync_api import sync_playwright

from scripts.pipeline.types import ShallowJob
from scripts.providers._shared.job_filter import is_relevant
from scripts.scrape_wellfound import (
    LOCATION_PRESETS, WELLFOUND_BASE,
    apply_filters, change_location, scroll_to_load_all, collect_wellfound,
)


def scrape_jobs(location: str, cdp_url: str) -> list[ShallowJob]:
    preset_key = location.lower()
    if preset_key not in LOCATION_PRESETS:
        raise ValueError(f"Unknown location: {location!r}")
    country_name = {"berlin": "Germany", "spain": "Spain"}.get(preset_key, location)
    location_query = LOCATION_PRESETS[preset_key]

    raw_rows: list[dict] = []
    with sync_playwright() as pw:
        browser = pw.chromium.connect_over_cdp(cdp_url)
        ctx = browser.contexts[0]
        page = ctx.new_page()
        try:
            page.goto(f"{WELLFOUND_BASE}/jobs", wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(2000)
            apply_filters(page)
            change_location(page, location_query)
            scroll_to_load_all(page)
            raw_rows = collect_wellfound(page, country_name)
        finally:
            page.close()

    jobs: list[ShallowJob] = []
    for r in raw_rows:
        if not r.get("title") or not r.get("company"):
            continue
        j = ShallowJob(
            provider="wellfound",
            title=r["title"],
            company=r["company"],
            url=r["url"],
            location=r.get("location", ""),
            country=r.get("country"),
            dedup_key=f"{r['company']}::{r['title']}",
            posting_date=None,
            salary_raw=r.get("salaryRaw") or None,
        )
        if is_relevant({"title": j.title}):
            jobs.append(j)
    return jobs
