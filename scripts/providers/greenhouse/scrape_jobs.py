from __future__ import annotations

from pathlib import Path
from urllib.parse import quote_plus

from playwright.sync_api import sync_playwright

from scripts.pipeline.types import ShallowJob
from scripts.providers._shared.job_filter import is_relevant
from scripts.scrape_greenhouse import GREENHOUSE_BASE, collect_greenhouse

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent


def _load_config() -> dict:
    try:
        import yaml  # noqa: PLC0415
        p = PROJECT_ROOT / "config" / "user.yaml"
        return yaml.safe_load(p.read_text()) or {} if p.exists() else {}
    except Exception:
        return {}


def scrape_jobs(
    cdp_url: str,
    titles: list[str] | None = None,
    db_path: str | None = None,
    _config: dict | None = None,
) -> list[ShallowJob]:
    cfg = _config if _config is not None else _load_config()
    locations: list[dict] = cfg.get("locations", [])
    if not locations:
        return []

    seen_urls: set[str] = set()
    all_raw: list[dict] = []

    with sync_playwright() as pw:
        browser = pw.chromium.connect_over_cdp(cdp_url)
        ctx = browser.contexts[0]
        page = ctx.new_page()
        try:
            for location in locations:
                country_code = location["country_code"]
                country = location["country"]
                city = location["city"]
                url_params = (
                    f"location={quote_plus(country)}&location_type=country"
                    f"&country_short_name={country_code}"
                )
                search = {
                    "label": f"{city} Remote",
                    "query": "",
                    "country": country,
                    "locationLabel": f"{city} Remote",
                    "url": f"{GREENHOUSE_BASE}?view=for-you&{url_params}&work_type[]=remote",
                }
                for r in collect_greenhouse(page, search):
                    if r.get("url") and r["url"] not in seen_urls:
                        seen_urls.add(r["url"])
                        all_raw.append(r)
        finally:
            page.close()

    jobs: list[ShallowJob] = []
    for r in all_raw:
        if not r.get("title") or not r.get("company"):
            continue
        relevant = is_relevant({"title": r["title"]})
        j = ShallowJob(
            provider="greenhouse",
            title=r["title"],
            company=r["company"],
            url=r["url"],
            location=r.get("location", ""),
            country=r.get("country"),
            dedup_key=f"{r['company']}::{r['title']}",
            posting_date=r.get("postingDate") or None,
            salary_raw=r.get("salaryRaw") or None,
            status="listed" if relevant else "skip",
        )
        jobs.append(j)

    if titles:
        jobs = [j for j in jobs if j.status == "skip" or any(t.lower() in j.title.lower() for t in titles)]
    return jobs
