#!/usr/bin/env python3
"""
Scrape Greenhouse job search results and save normalized JSON.

Usage:
  # Personalised "for-you" feed (locations from config/user.yaml):
  python3 scripts/scrape_greenhouse.py

  # Keyword search by title (use only if feed is insufficient):
  python3 scripts/scrape_greenhouse.py \
    --titles "Software Engineer" "AI Engineer"

  # Custom search URL:
  python3 scripts/scrape_greenhouse.py \
    --search-url "https://my.greenhouse.io/jobs?view=for-you&..." \
    --country Germany --location-label "Berlin"

Options:
  --titles <str...>       Job titles for keyword search (omit to use personalised feed)
  --search-url <url>      Raw search URL (can repeat; overrides --titles)
  --country <str>         Country label for output JSON (used with --search-url)
  --location-label <str>  Label for output filename (used with --search-url)
  --browser-profile <p>   Persistent Chromium profile dir (default: ~/.interviews-browser-profile)
  --cdp-url <url>         CDP endpoint (default: http://localhost:9222)
  --headless              Run headless (no visible browser window)
  --date <YYYY-MM-DD>     Override today's date in output filename
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.job_filter import is_relevant

LOCATION_PRESETS: dict[str, dict] = {
    "berlin": {"country": "Germany", "city": "Berlin, Germany"},
    "spain":  {"country": "Spain",   "city": "Spain"},
}

GREENHOUSE_BASE = "https://my.greenhouse.io/jobs"
DEFAULT_PROFILE = Path.home() / ".interviews-browser-profile"
PROJECT_ROOT = Path(__file__).parent.parent


COUNTRY_CODE_TO_PRESET: dict[str, str] = {
    "DE": "berlin",
    "ES": "spain",
}


def load_config() -> dict:
    user_yaml = PROJECT_ROOT / "config" / "user.yaml"
    if not user_yaml.exists():
        return {}
    try:
        import yaml  # noqa: PLC0415
        return yaml.safe_load(user_yaml.read_text()) or {}
    except Exception as e:
        print(f"[WARN] Could not load config/user.yaml: {e}", file=sys.stderr, flush=True)
        return {}


def config_location_keys(cfg: dict) -> list[str]:
    keys: list[str] = []
    for loc in cfg.get("locations", []):
        key = COUNTRY_CODE_TO_PRESET.get(loc.get("country_code", ""))
        if key and key not in keys:
            keys.append(key)
    return keys


def slugify(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")


def set_location_on_page(page, city_label: str) -> None:
    """Type city into the Greenhouse location filter via UI."""
    try:
        # Find the location combobox/input in the filter bar
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
            print(f"  [WARN] Location input not found — skipping location set", file=sys.stderr, flush=True)
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
            print(f"    Location → {city_label!r}", flush=True)
        else:
            page.keyboard.press("Enter")
            page.wait_for_timeout(1500)
            print(f"    Location → {city_label!r} (Enter)", flush=True)
    except Exception as e:
        print(f"  [WARN] set_location_on_page: {e}", file=sys.stderr, flush=True)


def set_work_type_on_page(page, preferred: str) -> None:
    """Set Work Type filter in Greenhouse UI from config work_style.preferred."""
    mapping = {"remote": "Remote", "hybrid": "Hybrid", "onsite": "On-site"}
    label = mapping.get(preferred.lower(), "Remote")
    try:
        btn = page.locator('button:has-text("Work type")').first
        if btn.count() == 0:
            print(f"  [WARN] Work type button not found", file=sys.stderr, flush=True)
            return
        btn.click()
        page.wait_for_timeout(800)
        opt = page.locator(
            f'[role="option"]:has-text("{label}"), '
            f'label:has-text("{label}")'
        ).first
        if opt.count() > 0:
            opt.click()
            page.wait_for_timeout(1000)
            print(f"    Work type → {label!r}", flush=True)
        else:
            page.keyboard.press("Escape")
            print(f"  [WARN] Work type option {label!r} not found", file=sys.stderr, flush=True)
    except Exception as e:
        print(f"  [WARN] set_work_type_on_page: {e}", file=sys.stderr, flush=True)


def search_on_page(page, title: str) -> None:
    """Type title into the Greenhouse search box and trigger search."""
    try:
        selectors = [
            'input[name="query"]',
            'input[type="search"]',
            'input[placeholder*="earch"]',
            'input[placeholder*="itle"]',
            'input[placeholder*="ob"]',
            'input[type="text"]',
        ]
        inp = None
        for sel in selectors:
            loc = page.locator(sel).first
            if loc.count() > 0:
                inp = loc
                break
        if inp is None:
            print(f"  [WARN] No search input found for title: {title!r}", file=sys.stderr, flush=True)
            return
        inp.click()
        page.wait_for_timeout(200)
        page.keyboard.press("Meta+a")
        page.keyboard.type(title, delay=30)
        page.wait_for_timeout(300)
        page.keyboard.press("Enter")
        page.wait_for_timeout(3000)
        print(f"    Typed search: {title!r}", flush=True)
    except Exception as e:
        print(f"  [WARN] search_on_page failed: {e}", file=sys.stderr, flush=True)


def scroll_to_load_all(page, max_scrolls: int = 6) -> int:
    """Scroll until no new job links appear or max_scrolls reached."""
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
            print("    No new cards — stopping scroll.", flush=True)
            break
        last = current
    return last


def is_auth_page(url: str) -> bool:
    return "/users/sign_in" in url


def collect_greenhouse(page, search: dict, skip_setup: bool = False) -> list[dict]:
    """Navigate to Greenhouse, set location + title via UI, collect job cards.

    When skip_setup=True, reuses the existing page state (location and work_type
    already set for the same location). Only updates the search query.
    Pass skip_setup=True for the 2nd+ title within the same location.
    """
    if not skip_setup:
        nav_url = search.get("url") or f"{GREENHOUSE_BASE}?view=for-you"
        page.goto(nav_url, wait_until="domcontentloaded", timeout=45000)
        page.wait_for_timeout(2000)

        if is_auth_page(page.url):
            print(f"\n⚠️  AUTH REQUIRED: Greenhouse login needed for {search['label']}.",
                  flush=True)
            print("Exiting with code 10 to signal pipeline pause.", flush=True)
            raise SystemExit(10)

        # Set location via UI (URL params are ignored by Greenhouse SPA)
        if search.get("city"):
            set_location_on_page(page, search["city"])

        # Set work type filter from config
        if search.get("work_type"):
            set_work_type_on_page(page, search["work_type"])

    # Type search term into UI
    if search.get("query"):
        search_on_page(page, search["query"])

    # Scroll to load all lazy results
    try:
        page.wait_for_load_state("networkidle", timeout=12000)
    except Exception:
        pass
    scroll_to_load_all(page)

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
                if (text.includes('Posted ') && text.includes('View job') && text.length < 900)
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


def enrich_greenhouse_job(page, row: dict) -> None:
    try:
        page.goto(row["url"], wait_until="domcontentloaded", timeout=12000)
        page.wait_for_timeout(500)
        details = page.evaluate(
            """() => {
            const lines = (document.body.innerText || '').split('\\n').map(v => v.trim()).filter(Boolean);
            const tm = document.title.match(/^Job Application for (.+?) at (.+)$/i);
            const title = (tm && tm[1]) || lines.find(l => /engineer|manager|developer|lead|architect/i.test(l)) || '';
            const company = (tm && tm[2]) || '';
            const location = lines.find(l => /remote|berlin|germany|spain|espa/i.test(l)) || '';

            // DOM selectors first; fall back to heuristic line scan
            const descEl = document.querySelector('#content')
                        || document.querySelector('#job_description')
                        || document.querySelector('.job-description')
                        || document.querySelector('[class*="description"]');
            let description = '';
            if (descEl) {
                description = (descEl.innerText || '').trim().slice(0, 2000);
            } else {
                description = lines
                    .filter(l => l.length > 70 && !/^https?:/.test(l) && !/cookie|privacy|terms|sign in/i.test(l))
                    .slice(0, 10).join(' ').slice(0, 2000);
            }
            const salaryRaw = lines.find(l =>
                /\\d/.test(l) && /[\\$€£]|USD|EUR|GBP|salary|compensation/i.test(l) &&
                !/cookie|privacy|terms|sign in|copyright/i.test(l)
            ) || '';
            const timeEl = document.querySelector('time[datetime]');
            let postingDate = '';
            if (timeEl) {
                const dt = timeEl.getAttribute('datetime') || '';
                const m = dt.match(/(\\d{4}-\\d{2}-\\d{2})/);
                if (m) postingDate = m[1];
            }
            if (!postingDate) {
                const dateLine = lines.find(l => /posted|updated/i.test(l) && /\\d{4}|\\d+\\s*(day|week|month)/i.test(l));
                if (dateLine) {
                    const iso = dateLine.match(/(\\d{4}-\\d{2}-\\d{2})/);
                    if (iso) postingDate = iso[1];
                }
            }
            return { title, company, location, description, salaryRaw, postingDate };
            }"""
        )
        if details["title"]:
            row["title"] = details["title"]
        if details["company"]:
            row["company"] = details["company"]
        if details["location"]:
            row["location"] = details["location"]
        if details["description"]:
            row["description"] = details["description"]
        if details.get("salaryRaw"):
            row["salaryRaw"] = details["salaryRaw"]
        if details.get("postingDate"):
            row["postingDate"] = details["postingDate"]
    except Exception as e:
        row["scrapeError"] = str(e)[:300]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--titles", nargs="+", help="Override: job titles to search")
    parser.add_argument("--search-url", dest="search_urls", action="append",
                        metavar="URL", help="Raw search URL (can repeat; overrides all other options)")
    parser.add_argument("--country", help="Country label (with --search-url)")
    parser.add_argument("--location-label", dest="location_label",
                        help="Location label for filename (with --search-url)")
    parser.add_argument("--output-dir", type=Path,
                        default=PROJECT_ROOT / "outputs" / "greenhouse" / "runs")
    parser.add_argument("--browser-profile", type=Path, default=DEFAULT_PROFILE,
                        help="[DEPRECATED] ignored — CDP uses existing Chrome")
    parser.add_argument("--cdp-url", default="http://localhost:9222")
    parser.add_argument("--headless", action="store_true", help="[DEPRECATED] ignored")
    parser.add_argument("--date", default=date.today().isoformat())
    args = parser.parse_args()

    cfg = load_config()
    titles: list[str] = args.titles or cfg.get("search_terms", [])
    work_type: str = cfg.get("work_style", {}).get("preferred", "remote")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    print(f"CDP: {args.cdp_url}", flush=True)

    from playwright.sync_api import sync_playwright  # noqa: PLC0415

    with sync_playwright() as pw:
        browser = pw.chromium.connect_over_cdp(args.cdp_url)
        context = browser.contexts[0]
        page = context.new_page()

        # ── Manual URL mode ──────────────────────────────────────────────────
        if args.search_urls:
            if not args.country or not args.location_label:
                print("--country and --location-label required with --search-url", file=sys.stderr)
                browser.close()
                return 2
            searches = [
                {"label": f"{args.country} - {args.location_label}", "query": "",
                 "country": args.country, "locationLabel": args.location_label, "url": url}
                for url in args.search_urls
            ]
            location_slug = slugify(args.location_label)
            output_file = args.output_dir / f"greenhouse_jobs_live_{args.date}_{location_slug}.json"
            _run_location(page, searches, output_file, args.date)
            browser.close()
            return 0

        # ── Config / preset mode ─────────────────────────────────────────────
        location_keys = config_location_keys(cfg)
        if not location_keys:
            print("No locations in config/user.yaml. Add locations with country_code DE or ES.",
                  file=sys.stderr)
            browser.close()
            return 2

        for location_key in location_keys:
            if location_key not in LOCATION_PRESETS:
                print(f"  [SKIP] Unknown preset {location_key!r}", file=sys.stderr, flush=True)
                continue
            preset = LOCATION_PRESETS[location_key]
            location_slug = slugify(location_key)
            output_file = args.output_dir / f"greenhouse_jobs_live_{args.date}_{location_slug}.json"

            if titles:
                searches = [
                    {"label": f"{t} - {location_key.title()} Remote", "query": t,
                     "city": preset["city"], "country": preset["country"],
                     "work_type": work_type,
                     "locationLabel": f"{location_key.title()} Remote"}
                    for t in titles
                ]
            else:
                searches = [
                    {"label": f"{location_key.title()} Remote", "query": "",
                     "city": preset["city"], "country": preset["country"],
                     "work_type": work_type,
                     "locationLabel": f"{location_key.title()} Remote"}
                ]

            print(f"\n=== {location_key.upper()} — {len(searches)} search(es) ===", flush=True)
            _run_location(page, searches, output_file, args.date)

        browser.close()
    return 0


def _run_location(page, searches: list[dict], output_file: Path, today: str) -> None:
    """Run all searches for one location, enrich, filter, and write file."""
    rows_by_url: dict[str, dict] = {}
    last_city: str | None = None
    for search in searches:
        print(f"  Scraping: {search['label']}", flush=True)
        current_city = search.get("city")
        skip_setup = last_city is not None and current_city == last_city
        try:
            cards = collect_greenhouse(page, search, skip_setup=skip_setup)
            last_city = current_city
            print(f"    Found {len(cards)} cards", flush=True)
            for card in cards:
                rows_by_url.setdefault(card["url"], card)
        except SystemExit:
            raise
        except Exception as e:
            print(f"    ERROR: {e}", file=sys.stderr, flush=True)

    rows = list(rows_by_url.values())

    # Filter before enrichment — is_relevant only needs title, no page visit required
    relevant_rows = [
        r for r in rows
        if r.get("url") and r.get("title") and r.get("company")
        and not re.match(r"^(Posted\b|Viewed\b|View job$|Applications$|Jobs$|Developers$)",
                         r.get("title", ""), re.I)
        and is_relevant(r)
    ]
    skip_rows = [
        r for r in rows
        if r.get("title") and r.get("company")
        and r not in relevant_rows
    ]
    print(f"  Profile filter: {len(relevant_rows)} relevant, {len(skip_rows)} skipped", flush=True)

    print(f"Enriching {len(relevant_rows)} relevant jobs...", flush=True)
    for i, row in enumerate(relevant_rows):
        print(f"  [{i+1}/{len(relevant_rows)}] {row['url'][:80]}", flush=True)
        enrich_greenhouse_job(page, row)

    for row in skip_rows:
        row["_skip"] = True

    all_rows = relevant_rows + skip_rows
    output_file.write_text(json.dumps(all_rows, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({
        "out": str(output_file), "count": len(final_rows),
        "dropped": rows_before - len(final_rows),
        "countries": sorted({r.get("country", "") for r in final_rows}),
        "missing_descriptions": sum(1 for r in final_rows if not r.get("description")),
    }, indent=2), flush=True)


if __name__ == "__main__":
    raise SystemExit(main())
