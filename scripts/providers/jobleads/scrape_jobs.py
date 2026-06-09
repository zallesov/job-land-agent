from __future__ import annotations

import re
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

from scripts.pipeline.types import ShallowJob
from scripts.providers._shared.job_filter import is_relevant

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
JOBLEADS_BASE = "https://www.jobleads.com/es/jobs"


def _parse_args(*args, titles=None, db_path=None, _config=None):
    if not args:
        raise TypeError("scrape_jobs() missing required positional argument: cdp_url")
    cfg = _config if _config is not None else _load_config()
    if isinstance(args[0], dict):
        if len(args) < 2:
            raise TypeError("scrape_jobs() missing required cdp_url argument")
        cdp_url = args[1]
        locations = [args[0]]
    else:
        cdp_url = args[0]
        locations = cfg.get("locations", [])
    return cdp_url, cfg, locations, titles, db_path


def _load_config() -> dict:
    try:
        import yaml  # noqa: PLC0415
        p = PROJECT_ROOT / "config" / "user.yaml"
        return yaml.safe_load(p.read_text()) or {} if p.exists() else {}
    except Exception:
        return {}


def _is_auth_page(url: str) -> bool:
    return bool(re.search(r"/external-home|accounts\.google\.com|modal=login|sign.in", url))


def _is_unauthenticated(page) -> bool:
    try:
        body = (page.content() or "").lower()
        return "solo para miembros registrados" in body
    except Exception:
        return False


def _country_already_selected(page, country: str) -> bool:
    try:
        active = page.evaluate(
            """() => {
            const el = document.querySelector('a.country-selector-list__btn_active');
            return el ? (el.textContent || '').trim() : '';
            }"""
        )
        return isinstance(active, str) and active.strip().lower() == country.strip().lower()
    except Exception:
        return False


def _ensure_country(page, country: str) -> None:
    if not country or _country_already_selected(page, country):
        return

    page.locator('[data-testid="ui-select-search-country-dropdown-trigger"]').first.click()
    page.wait_for_timeout(300)
    page.locator('[data-testid="ui-select-search-country-dropdown-input"]').first.fill(country)
    page.wait_for_timeout(300)
    page.evaluate(
        """(country) => {
        const link = [...document.querySelectorAll('a.country-selector-list__btn')]
            .find(a => ((a.textContent || '').trim().toLowerCase() === country.toLowerCase()));
        if (!link) throw new Error(`country not found: ${country}`);
        link.click();
        }""",
        country,
    )
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_timeout(1000)


def _ensure_remote(page) -> None:
    current = page.locator('[data-testid="new-sidebar-filter-select-job-location-type-ui-input"]').first.input_value().strip()
    if current.lower() == "remote":
        return

    page.locator('[data-testid="new-sidebar-filter-select-job-location-type-ui-input"]').first.click()
    page.wait_for_timeout(200)
    page.evaluate(
        """() => {
        const option = [...document.querySelectorAll('div,span,button,a,label')]
            .find(el => el.offsetParent !== null && ((el.textContent || '').trim() === 'Remote'));
        if (!option) throw new Error('Remote option not found');
        option.click();
        }"""
    )
    page.wait_for_timeout(300)


def _run_search(page, search: dict) -> None:
    page.goto(JOBLEADS_BASE, wait_until="domcontentloaded", timeout=45000)
    page.wait_for_timeout(1500)

    if _is_auth_page(page.url):
        print("\n⚠️  AUTH REQUIRED: JobLeads login needed.", flush=True)
        raise SystemExit(10)

    if _is_unauthenticated(page):
        print("\n⚠️  AUTH REQUIRED: JobLeads session not authenticated.", flush=True)
        raise SystemExit(10)

    _ensure_country(page, search["country"])

    keyword = page.locator('[data-testid="search-form-keyword-ui-input"]').first
    keyword.click()
    keyword.fill(search["query"])

    location = page.locator('[data-testid="search-form-location-input"]').first
    location.click()
    location.fill(search["city"])
    page.wait_for_timeout(500)

    if search.get("remote_only"):
        _ensure_remote(page)

    page.locator('button[type="submit"]').first.click()
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_timeout(2000)


def collect_jobleads(page, search: dict) -> list[dict]:
    _run_search(page, search)

    try:
        page.wait_for_selector('a[href*="/job/"]', timeout=20000)
    except Exception:
        print(f"  No job links found for {search['label']}", file=sys.stderr, flush=True)
        return []

    for _ in range(8):
        page.evaluate("() => window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(700)

    cards: list[dict] = page.evaluate(
        """(search) => {
        function hasMarker(text) {
            const t = (text || '').toLowerCase();
            return [
                'remote', 'hybrid', 'on-site', 'on site', 'vor ort', 'a distancia',
                'full time', 'part time', 'vollzeit', 'teilzeit',
                'days ago', 'day ago', 'today', 'heute', 'hace ', 'vor '
            ].some(marker => t.includes(marker));
        }
        function looksLikeSalary(line) {
            return ['EUR', 'USD', '€', '$'].some(token => (line || '').includes(token));
        }
        function looksLikePosted(line) {
            const t = (line || '').toLowerCase();
            return (
                t.includes('hace ') || t.includes(' day ago') || t.includes(' days ago') ||
                t.includes(' week ago') || t.includes(' weeks ago') ||
                t.includes(' month ago') || t.includes(' months ago') ||
                t.startsWith('vor ') || t === 'heute' || t === 'today'
            );
        }
        function cardFor(anchor) {
            let node = anchor.parentElement;
            let best = anchor.parentElement;
            while (node && node !== document.body) {
                const text = (node.innerText || '').trim();
                if (text.length > 40 && text.length < 2000 && hasMarker(text)) {
                    best = node;
                }
                node = node.parentElement;
            }
            return best;
        }
        const seen = new Set();
        return Array.from(document.querySelectorAll('a[href*="/job/"]'))
            .map(anchor => {
                const url = new URL(anchor.href, window.location.href).href;
                if (seen.has(url)) return null;
                seen.add(url);
                const card = cardFor(anchor);
                const lines = (card.innerText || '').split('\\n').map(v => v.trim()).filter(Boolean);
                const title = (anchor.innerText || lines[0] || '').trim();
                const firstIdx = lines.findIndex(l => l === title);
                let rest = firstIdx >= 0 ? lines.slice(firstIdx + 1) : lines.slice(1);
                if (rest[0] === title) rest = rest.slice(1);
                const salaryIdx = rest.findIndex(looksLikeSalary);
                const postedRelative = rest.find(looksLikePosted) || '';
                const remoteIdx = rest.findIndex(l => hasMarker(l) && ['remote', 'hybrid', 'on-site', 'on site', 'vor ort', 'a distancia'].some(m => (l || '').toLowerCase().includes(m)));
                const company = rest[0] || '';
                let location = '';
                if (remoteIdx > 0) location = rest[remoteIdx - 1];
                else if (salaryIdx > 1) location = rest[salaryIdx - 1];
                const salaryRaw = salaryIdx >= 0 ? rest[salaryIdx] : '';
                return {
                    provider: 'jobleads',
                    company,
                    title,
                    url,
                    description: '',
                    applyUrl: '',
                    location,
                    country: search.country,
                    postedRelative,
                    salaryRaw,
                    searchLabel: search.label,
                };
            })
            .filter(Boolean);
        }""",
        search,
    )
    return cards


def scrape_jobs(
    *args,
    titles: list[str] | None = None,
    db_path: str | None = None,
    _config: dict | None = None,
) -> list[ShallowJob]:
    cdp_url, cfg, locations, titles, db_path = _parse_args(
        *args, titles=titles, db_path=db_path, _config=_config
    )
    if not locations:
        return []

    seen_urls: set[str] = set()
    all_raw: list[dict] = []

    with sync_playwright() as pw:
        browser = pw.chromium.connect_over_cdp(cdp_url)
        ctx = browser.contexts[0]
        page = ctx.new_page()
        page.bring_to_front()
        try:
            title_queries = titles or cfg.get("search_terms") or [""]
            remote_only = (cfg.get("work_style", {}) or {}).get("preferred") == "remote"
            for location in locations:
                country = location["country"]
                city = location["city"]
                for title in title_queries:
                    search = {
                        "label": f"{title or 'Any title'} | {city}",
                        "query": title,
                        "city": city,
                        "country": country,
                        "remote_only": remote_only,
                    }
                    for r in collect_jobleads(page, search):
                        if r.get("url") and r["url"] not in seen_urls:
                            seen_urls.add(r["url"])
                            all_raw.append(r)
        finally:
            page.close()

    jobs: list[ShallowJob] = []
    for r in all_raw:
        if not r.get("title") or not r.get("company"):
            continue
        status = "listed" if is_relevant(r) else "skip"
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
            status=status,
        )
        jobs.append(j)
    return jobs
