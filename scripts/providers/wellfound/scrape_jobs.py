from __future__ import annotations
from playwright.sync_api import sync_playwright

from scripts.pipeline.types import ShallowJob
from scripts.providers._shared.job_filter import is_relevant
from scripts.scrape_wellfound import (
    WELLFOUND_BASE,
    apply_filters, change_location, scroll_to_load_all, collect_wellfound,
)


def scrape_jobs(
    location: dict,
    cdp_url: str,
    titles: list[str] | None = None,
    db_path: str | None = None,
) -> list[ShallowJob]:
    city = location["city"]
    country = location["country"]
    location_query = f"{city}, {country}"

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
            raw_rows = collect_wellfound(page, country)
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

    if titles:
        jobs = [j for j in jobs if any(t.lower() in j.title.lower() for t in titles)]
    return jobs
