from __future__ import annotations
from playwright.sync_api import sync_playwright

from scripts.pipeline.types import ShallowJob
from scripts.providers._shared.job_filter import is_relevant
from scripts.scrape_jobleads import JOBLEADS_BASE, collect_jobleads


def scrape_jobs(
    location: dict,
    cdp_url: str,
    titles: list[str] | None = None,
) -> list[ShallowJob]:
    country_code = location["country_code"]
    country = location["country"]
    city = location["city"]
    url_params = (
        f"location_country={country_code}"
        f"&filter_by_contractType=full_time"
        f"&filter_by_remote=remote"
        f"&minSalary=100000"
    )
    search = {
        "label": f"{city} Remote",
        "query": "",
        "country": country,
        "url": f"{JOBLEADS_BASE}?view=for-you&{url_params}",
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

    if titles:
        jobs = [j for j in jobs if any(t.lower() in j.title.lower() for t in titles)]
    return jobs
