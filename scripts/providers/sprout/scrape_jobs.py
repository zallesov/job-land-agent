from __future__ import annotations
from playwright.sync_api import sync_playwright

from scripts.pipeline.types import ShallowJob
from scripts.providers._shared.job_filter import is_relevant
from scripts.scrape_sprout import SPROUT_BASE, collect_sprout

DEFAULT_TITLES = [
    "Software Engineer", "Backend Engineer", "AI Engineer",
    "Platform Engineer", "Engineering Manager",
]


def scrape_jobs(
    location: dict,
    cdp_url: str,
    titles: list[str] | None = None,
    db_path: str | None = None,
) -> list[ShallowJob]:
    city = location["city"]
    country = location["country"]
    effective_titles = titles or DEFAULT_TITLES

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
                titles=effective_titles,
                location=city,
                country=country,
                db_path=db_path,
            )
        finally:
            page.close()

    jobs: list[ShallowJob] = []
    for r in raw_rows:
        if not r.get("title") or not r.get("company"):
            continue
        relevant = is_relevant({"title": r["title"]})
        j = ShallowJob(
            provider="sprout",
            title=r["title"],
            company=r["company"],
            url=r["url"],
            location=r.get("location", ""),
            country=r.get("country") or country,
            dedup_key=f"{r['company']}::{r['title']}",
            posting_date=None,
            salary_raw=r.get("salary") or None,
            status="listed" if relevant else "skip",
        )
        jobs.append(j)
    return jobs
