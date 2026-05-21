from __future__ import annotations
from playwright.sync_api import sync_playwright

from scripts.pipeline.types import ShallowJob
from scripts.providers._shared.job_filter import is_relevant
from scripts.scrape_jobleads import (
    LOCATION_PRESETS, build_feed_url, collect_jobleads,
)


def scrape_jobs(location: str, cdp_url: str) -> list[ShallowJob]:
    preset_key = location.lower()
    if preset_key not in LOCATION_PRESETS:
        raise ValueError(f"Unknown location: {location!r}")
    preset = LOCATION_PRESETS[preset_key]
    search = {
        "label": f"{location.title()} Remote",
        "query": "",
        "country": preset["country"],
        "url": build_feed_url(preset),
    }

    raw_rows: list[dict] = []
    with sync_playwright() as pw:
        browser = pw.chromium.connect_over_cdp(cdp_url)
        ctx = browser.contexts[0]
        page = ctx.new_page()
        try:
            raw_rows = collect_jobleads(page, search)
        finally:
            page.close()

    jobs: list[ShallowJob] = []
    for r in raw_rows:
        if not r.get("title") or not r.get("company"):
            continue
        j = ShallowJob(
            provider="jobleads",
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
