from __future__ import annotations

import sys
from pathlib import Path
from urllib.parse import quote_plus

from playwright.sync_api import sync_playwright

from scripts.pipeline.types import ShallowJob
from scripts.providers._shared.job_filter import is_relevant

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent

GREENHOUSE_BASE = "https://my.greenhouse.io/jobs"


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
    return "/users/sign_in" in url


def _set_location_on_page(page, city_label: str) -> None:
    try:
        inp = None
        for sel in [
            'input[placeholder*="ocation" i]',
            'input[aria-label*="ocation" i]',
            '[role="combobox"]',
        ]:
            el = page.locator(sel).first
            if el.count() > 0:
                inp = el
                break
        if inp is None:
            print("  [WARN] Location input not found", file=sys.stderr, flush=True)
            return
        inp.click()
        page.wait_for_timeout(300)
        page.keyboard.press("Meta+a")
        page.keyboard.press("Control+a")
        page.keyboard.type(city_label, delay=50)
        page.wait_for_timeout(2000)
        opt = page.locator('[role="option"]').first
        if opt.count() > 0:
            opt.click()
            page.wait_for_timeout(2000)
        else:
            page.keyboard.press("Enter")
            page.wait_for_timeout(1500)
    except Exception as e:
        print(f"  [WARN] set_location_on_page: {e}", file=sys.stderr, flush=True)


def _set_work_type_on_page(page, preferred: str) -> None:
    mapping = {"remote": "Remote", "hybrid": "Hybrid", "onsite": "On-site"}
    label = mapping.get(preferred.lower(), "Remote")
    try:
        btn = page.locator('button:has-text("Work type")').first
        if btn.count() == 0:
            return
        btn.click()
        page.wait_for_timeout(800)
        opt = page.locator(
            f'[role="option"]:has-text("{label}"), label:has-text("{label}")'
        ).first
        if opt.count() > 0:
            opt.click()
            page.wait_for_timeout(1000)
        else:
            page.keyboard.press("Escape")
    except Exception as e:
        print(f"  [WARN] set_work_type_on_page: {e}", file=sys.stderr, flush=True)


def _search_on_page(page, title: str) -> None:
    try:
        selectors = [
            'input[name="query"]', 'input[type="search"]',
            'input[placeholder*="earch"]', 'input[placeholder*="itle"]',
            'input[placeholder*="ob"]', 'input[type="text"]',
        ]
        inp = None
        for sel in selectors:
            loc = page.locator(sel).first
            if loc.count() > 0:
                inp = loc
                break
        if inp is None:
            return
        inp.click()
        page.wait_for_timeout(200)
        page.keyboard.press("Meta+a")
        page.keyboard.type(title, delay=30)
        page.wait_for_timeout(300)
        page.keyboard.press("Enter")
        page.wait_for_timeout(3000)
    except Exception as e:
        print(f"  [WARN] search_on_page: {e}", file=sys.stderr, flush=True)


def _scroll_to_load_all(page, max_scrolls: int = 6) -> int:
    def count_jobs() -> int:
        return page.evaluate("""() => Array.from(document.querySelectorAll('a[href]')).filter(a => {
            const href = a.getAttribute('href') || '';
            try {
                const url = new URL(href, window.location.href);
                if (url.hostname === 'my.greenhouse.io') return false;
                return /greenhouse\\.io$/.test(url.hostname) ||
                       url.searchParams.has('gh_jid') ||
                       url.searchParams.get('gh_src') === 'my.greenhouse.search';
            } catch(e) { return false; }
        }).length""")

    last = count_jobs()
    for i in range(max_scrolls):
        page.evaluate("() => window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(2000)
        current = count_jobs()
        print(f"    Scroll {i + 1}: {current} job links visible", flush=True)
        if current == last:
            break
        last = current
    return last


def collect_greenhouse(page, search: dict, skip_setup: bool = False) -> list[dict]:
    if not skip_setup:
        nav_url = search.get("url") or f"{GREENHOUSE_BASE}?view=for-you"
        page.goto(nav_url, wait_until="domcontentloaded", timeout=45000)
        page.wait_for_timeout(2000)
        if _is_auth_page(page.url):
            print("\n⚠️  AUTH REQUIRED: Greenhouse login needed.", flush=True)
            raise SystemExit(10)
        if search.get("city"):
            _set_location_on_page(page, search["city"])
        if search.get("work_type"):
            _set_work_type_on_page(page, search["work_type"])
    if search.get("query"):
        _search_on_page(page, search["query"])
    try:
        page.wait_for_load_state("networkidle", timeout=12000)
    except Exception:
        pass
    _scroll_to_load_all(page)
    rows: list[dict] = page.evaluate(
        """(search) => {
        function textLines(node) {
            return (node.innerText || '').split('\\n').map(v => v.trim()).filter(Boolean);
        }
        function resultContainer(anchor) {
            let node = anchor.parentElement;
            let best = anchor.parentElement;
            while (node && node !== document.body) {
                const text = (node.innerText || '').trim();
                if (text.includes('Posted ') && text.includes('View job') && text.length < 900 && text.length > 100)
                    return node;
                if (text.length > 20 && text.length < 900) best = node;
                node = node.parentElement;
            }
            return best;
        }
        const anchors = Array.from(document.querySelectorAll('a[href]')).filter(a => {
            const href = a.getAttribute('href') || '';
            if (/sign_out|users\\/|privacy|terms|mailto:/i.test(href)) return false;
            const url = new URL(href, window.location.href);
            if (url.hostname === 'my.greenhouse.io') return false;
            return (
                /greenhouse\\.io$/i.test(url.hostname) ||
                url.searchParams.has('gh_jid') ||
                url.searchParams.get('gh_src') === 'my.greenhouse.search'
            );
        });
        const seen = new Set();
        return anchors.map(anchor => {
            const url = new URL(anchor.getAttribute('href'), window.location.href).href.split('#')[0];
            if (seen.has(url)) return null;
            seen.add(url);
            const container = resultContainer(anchor);
            let lines = textLines(container).filter(l => l !== 'View job');
            if (lines[0] && /^[A-Z]$/.test(lines[0])) lines = lines.slice(1);
            const anchorText = (anchor.innerText || '').trim();
            const title =
                anchorText && anchorText !== 'View job' && anchorText.length <= 140
                    ? anchorText
                    : lines.find(l => /engineer|manager|developer|lead|architect/i.test(l)) || lines[0] || anchorText.slice(0,140);
            const company = lines.find(l =>
                l !== title &&
                !/remote|full-time|part-time|posted|viewed|berlin|germany|spain|espa/i.test(l)
            ) || '';
            const location = lines.filter(l => /remote|berlin|germany|spain|espa/i.test(l)).join(', ') || search.locationLabel;
            return { provider: 'greenhouse', company, title, url, description: '', applyUrl: url,
                     location, country: search.country, postingDate: '', searchLabel: search.label, searchQuery: search.query };
        }).filter(Boolean);
        }""",
        search,
    )
    return rows


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
        status = "listed" if is_relevant(r) else "skip"
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
            status=status,
        )
        jobs.append(j)

    if titles:
        jobs = [j for j in jobs if any(t.lower() in j.title.lower() for t in titles)]
    return jobs
