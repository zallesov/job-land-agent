from __future__ import annotations

import urllib.parse
from pathlib import Path

from playwright.sync_api import sync_playwright

from scripts.pipeline.types import ShallowJob
from scripts.providers._shared.job_filter import is_relevant
from scripts.scrape_wellfound import (
    WELLFOUND_BASE,
    apply_filters, change_location, scroll_to_load_all, collect_wellfound,
    wait_for_search_results,
)

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent

# Plain scripting — no LLM needed
COUNTRY_TO_CONTINENT: dict[str, str] = {
    "DE": "Europe", "AT": "Europe", "CH": "Europe", "FR": "Europe",
    "NL": "Europe", "BE": "Europe", "GB": "Europe", "IE": "Europe",
    "ES": "Europe", "PT": "Europe", "IT": "Europe", "PL": "Europe",
    "CZ": "Europe", "SE": "Europe", "NO": "Europe", "DK": "Europe",
    "FI": "Europe", "HU": "Europe", "RO": "Europe", "GR": "Europe",
    "US": "United States",
    "CA": "Canada",
    "AU": "Australia",
    "NZ": "New Zealand",
    "SG": "Singapore",
    "IN": "India",
    "JP": "Japan",
    "IL": "Israel",
    "BR": "Brazil",
    "MX": "Mexico",
    "ZA": "South Africa",
}


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
    work_style: str = cfg.get("work_style", {}).get("preferred", "remote")
    remote = work_style == "remote"
    search_terms: list[str] = titles or cfg.get("search_terms") or ["Software Engineer"]

    configured_locations: list[dict] = cfg.get("locations", [])

    if remote:
        # Map country codes → continents, deduplicate
        seen: set[str] = set()
        wellfound_locations: list[str] = []
        for loc in configured_locations:
            continent = COUNTRY_TO_CONTINENT.get(loc.get("country_code", ""), "Europe")
            if continent not in seen:
                seen.add(continent)
                wellfound_locations.append(continent)
    else:
        # Use city + country as location filter
        seen = set()
        wellfound_locations = []
        for loc in configured_locations:
            label = f"{loc['city']}, {loc['country']}"
            if label not in seen:
                seen.add(label)
                wellfound_locations.append(label)

    raw_rows: list[dict] = []
    seen_urls: set[str] = set()

    with sync_playwright() as pw:
        browser = pw.chromium.connect_over_cdp(cdp_url)
        ctx = browser.contexts[0]
        page = ctx.new_page()
        try:
            for wf_location in wellfound_locations:
                for role in search_terms:
                    url_params: dict[str, str] = {"role": role, "salary_min": "100000"}
                    if remote:
                        url_params["remote"] = "true"
                    nav_url = f"{WELLFOUND_BASE}/jobs?" + urllib.parse.urlencode(url_params)
                    page.goto(nav_url, wait_until="domcontentloaded", timeout=30000)
                    page.wait_for_timeout(2000)

                    if not wait_for_search_results(page, timeout=15000):
                        continue

                    apply_filters(page, work_style=work_style)
                    page.wait_for_timeout(1500)
                    change_location(page, wf_location)
                    page.wait_for_timeout(1500)
                    scroll_to_load_all(page)

                    rows = collect_wellfound(page, wf_location)
                    for r in rows:
                        if r.get("url") and r["url"] not in seen_urls:
                            seen_urls.add(r["url"])
                            raw_rows.append(r)
        finally:
            page.close()

    jobs: list[ShallowJob] = []
    for r in raw_rows:
        if not r.get("title") or not r.get("company"):
            continue
        relevant = is_relevant({"title": r["title"]})
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
            status="listed" if relevant else "skip",
        )
        jobs.append(j)

    if titles:
        jobs = [j for j in jobs if j.status == "skip" or any(t.lower() in j.title.lower() for t in titles)]
    return jobs
