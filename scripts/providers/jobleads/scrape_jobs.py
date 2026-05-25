from __future__ import annotations

import re
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

from scripts.pipeline.types import ShallowJob

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent

JOBLEADS_BASE = "https://www.jobleads.com/search/jobs"


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


def collect_jobleads(page, search: dict) -> list[dict]:
    page.goto(search["url"], wait_until="domcontentloaded", timeout=45000)
    page.wait_for_timeout(1500)

    if _is_auth_page(page.url):
        print("\n⚠️  AUTH REQUIRED: JobLeads login needed.", flush=True)
        raise SystemExit(10)

    if _is_unauthenticated(page):
        print("\n⚠️  AUTH REQUIRED: JobLeads session not authenticated.", flush=True)
        raise SystemExit(10)

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
        function cardFor(anchor) {
            let node = anchor.parentElement;
            let best = anchor.parentElement;
            while (node && node !== document.body) {
                const text = (node.innerText || '').trim();
                if (text.includes('Jornada completa') && text.includes('Hace ') && text.length < 1400)
                    best = node;
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
                const salaryIdx = rest.findIndex(l => /EUR|€/.test(l));
                const postedRelative = rest.find(l => /^(Hace\\s+\\d+|(\\d+)\\s+(day|days|Tag|Tage|week|weeks|month|months)\\s+(ago)?|vor\\s+\\d+)/i.test(l)) || '';
                const remoteIdx = rest.findIndex(l => /A distancia|Remote/i.test(l));
                const company = rest[0] || '';
                let location = '';
                if (remoteIdx > 0) location = rest[remoteIdx - 1];
                else if (salaryIdx > 1) location = rest[salaryIdx - 1];
                const salaryRaw = salaryIdx >= 0 ? rest[salaryIdx] : '';
                return { provider: 'jobleads', company, title, url, description: '', applyUrl: '',
                         location, country: search.country, postedRelative, salaryRaw, searchLabel: search.label };
            })
            .filter(Boolean);
        }""",
        search,
    )
    return cards


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
        page.bring_to_front()
        try:
            for location in locations:
                country_code = location["country_code"]
                country = location["country"]
                city = location["city"]
                url_params = (
                    f"location_country={country_code}"
                    f"&filter_by_contractType=full_time"
                    f"&filter_by_remote=remote"
                )
                search = {
                    "label": f"{city} Remote",
                    "query": "",
                    "country": country,
                    "url": f"{JOBLEADS_BASE}?view=for-you&{url_params}",
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
            status="new",
        )
        jobs.append(j)

    if titles:
        jobs = [j for j in jobs if any(t.lower() in j.title.lower() for t in titles)]
    return jobs
