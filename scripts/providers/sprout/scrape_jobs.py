from __future__ import annotations

from pathlib import Path

from playwright.sync_api import sync_playwright

from scripts.pipeline.types import ShallowJob
from scripts.providers._shared.job_filter import is_relevant
from scripts.scrape_sprout import SPROUT_BASE, collect_sprout

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent

DEFAULT_TITLES = [
    "Software Engineer", "Backend Engineer", "AI Engineer",
    "Platform Engineer", "Engineering Manager",
]


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
    search_terms = titles or cfg.get("search_terms") or DEFAULT_TITLES

    seen_urls: set[str] = set()
    all_raw: list[dict] = []

    with sync_playwright() as pw:
        browser = pw.chromium.connect_over_cdp(cdp_url)
        ctx = browser.contexts[0]
        page = ctx.new_page()
        try:
            page.goto(f"{SPROUT_BASE}/jobs", wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(2000)
            for location in locations:
                rows = collect_sprout(
                    page,
                    titles=search_terms,
                    location=location["city"],
                    country=location["country"],
                    db_path=db_path,
                )
                for r in rows:
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
            provider="sprout",
            title=r["title"],
            company=r["company"],
            url=r["url"],
            location=r.get("location", ""),
            country=r.get("country") or "",
            dedup_key=f"{r['company']}::{r['title']}",
            posting_date=None,
            salary_raw=r.get("salary") or None,
            status="new" if relevant else "skip",
        )
        jobs.append(j)
    return jobs
