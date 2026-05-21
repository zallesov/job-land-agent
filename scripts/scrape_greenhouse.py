#!/usr/bin/env python3
"""
Scrape Greenhouse job search results and save normalized JSON.

Usage:
  # Named location preset — personalised "for-you" feed (default):
  python3 scripts/scrape_greenhouse.py --location berlin
  python3 scripts/scrape_greenhouse.py --location spain

  # Keyword search by title (use only if feed is insufficient):
  python3 scripts/scrape_greenhouse.py \
    --location berlin \
    --titles "Software Engineer" "AI Engineer"

  # Custom search URL:
  python3 scripts/scrape_greenhouse.py \
    --search-url "https://my.greenhouse.io/jobs?view=for-you&..." \
    --country Germany --location-label "Berlin"

Options:
  --location <name>       Named preset: berlin | spain
  --titles <str...>       Job titles for keyword search (omit to use personalised feed)
  --search-url <url>      Raw search URL (can repeat; overrides --location + --titles)
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
from urllib.parse import quote_plus

from scripts.job_filter import is_relevant

# ---------------------------------------------------------------------------
# Named location presets  (location label → Greenhouse URL params + country)
# ---------------------------------------------------------------------------
LOCATION_PRESETS: dict[str, dict] = {
    "berlin": {
        "country": "Germany",
        "url_params": (
            "location=Berlin%2C%20Germany"
            "&lat=52.524932&lon=13.407032"
            "&location_type=locality"
            "&country_short_name=DE"
            "&state_short_name=BE"
        ),
    },
    "spain": {
        "country": "Spain",
        "url_params": "location=Spain&location_type=country&country_short_name=ES",
    },
}

GREENHOUSE_BASE = "https://my.greenhouse.io/jobs"
DEFAULT_PROFILE = Path.home() / ".interviews-browser-profile"
PROJECT_ROOT = Path(__file__).parent.parent


def slugify(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")


def build_feed_url(preset: dict) -> str:
    return f"{GREENHOUSE_BASE}?view=for-you&{preset['url_params']}&work_type[]=remote"


def build_title_url(title: str, preset: dict) -> str:
    return (
        f"{GREENHOUSE_BASE}"
        f"?query={quote_plus(title)}"
        f"&{preset['url_params']}"
        f"&work_type[]=remote"
    )


def is_auth_page(url: str) -> bool:
    return "/users/sign_in" in url


def collect_greenhouse(page, search: dict) -> list[dict]:
    """Navigate to one search URL and collect job cards."""
    page.goto(search["url"], wait_until="domcontentloaded", timeout=45000)
    page.wait_for_timeout(1500)

    if is_auth_page(page.url):
        print(f"\n⚠️  AUTH REQUIRED: Greenhouse login needed for {search['label']}.",
              flush=True)
        print("Please log in to Greenhouse in the Chrome browser window, then re-run.",
              flush=True)
        print("Exiting with code 10 to signal pipeline pause.", flush=True)
        raise SystemExit(10)

    # Scroll to load lazy content
    try:
        page.wait_for_load_state("networkidle", timeout=12000)
    except Exception:
        pass
    for _ in range(6):
        page.evaluate("() => window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(600)

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
    parser.add_argument("--location", help="Named preset: berlin | spain")
    parser.add_argument("--titles", nargs="+", help="Job titles to search")
    parser.add_argument("--search-url", dest="search_urls", action="append",
                        metavar="URL", help="Raw search URL (can repeat)")
    parser.add_argument("--country", help="Country label (with --search-url)")
    parser.add_argument("--location-label", dest="location_label",
                        help="Location label for filename (with --search-url)")
    parser.add_argument("--output-dir", type=Path,
                        default=PROJECT_ROOT / "outputs" / "greenhouse" / "runs")
    parser.add_argument("--browser-profile", type=Path, default=DEFAULT_PROFILE,
                        help="[DEPRECATED] CDP connection uses existing Chrome profile")
    parser.add_argument("--cdp-url", default="http://localhost:9222",
                        help="CDP endpoint (default: http://localhost:9222)")
    parser.add_argument("--headless", action="store_true",
                        help="[DEPRECATED] CDP uses existing Chrome — ignored")
    parser.add_argument("--date", default=date.today().isoformat())
    args = parser.parse_args()

    # Build search list
    searches: list[dict] = []

    if args.search_urls:
        if not args.country or not args.location_label:
            print("--country and --location-label required with --search-url", file=sys.stderr)
            return 2
        for url in args.search_urls:
            searches.append({
                "label": f"{args.country} - {args.location_label}",
                "query": "",
                "country": args.country,
                "locationLabel": args.location_label,
                "url": url,
            })
    elif args.location:
        preset_key = args.location.lower()
        if preset_key not in LOCATION_PRESETS:
            print(f"Unknown location preset: {args.location!r}. Known: {list(LOCATION_PRESETS)}", file=sys.stderr)
            return 2
        preset = LOCATION_PRESETS[preset_key]
        if args.titles:
            for title in args.titles:
                searches.append({
                    "label": f"{title} - {args.location.title()} Remote",
                    "query": title,
                    "country": preset["country"],
                    "locationLabel": f"{args.location.title()} Remote",
                    "url": build_title_url(title, preset),
                })
        else:
            searches.append({
                "label": f"{args.location.title()} Remote",
                "query": "",
                "country": preset["country"],
                "locationLabel": f"{args.location.title()} Remote",
                "url": build_feed_url(preset),
            })
    else:
        print("Provide --location <preset> or --search-url <url>", file=sys.stderr)
        return 2

    location_slug = slugify(args.location_label if args.search_urls else args.location)
    output_file = args.output_dir / f"greenhouse_jobs_live_{args.date}_{location_slug}.json"
    args.output_dir.mkdir(parents=True, exist_ok=True)

    print(f"CDP: {args.cdp_url}", flush=True)
    print(f"Searches: {[s['label'] for s in searches]}", flush=True)
    print(f"Output: {output_file}", flush=True)

    from playwright.sync_api import sync_playwright  # noqa: PLC0415

    with sync_playwright() as pw:
        # Connect to existing Chrome via CDP — inherits profile, auth, cookies
        browser = pw.chromium.connect_over_cdp(args.cdp_url)
        context = browser.contexts[0]
        page = context.new_page()

        rows_by_url: dict[str, dict] = {}
        for search in searches:
            print(f"  Scraping: {search['label']}", flush=True)
            try:
                cards = collect_greenhouse(page, search)
                print(f"    Found {len(cards)} cards", flush=True)
                for card in cards:
                    rows_by_url.setdefault(card["url"], card)
            except Exception as e:
                print(f"    ERROR: {e}", file=sys.stderr, flush=True)
                browser.close()
                return 1

        rows = list(rows_by_url.values())
        print(f"Enriching {len(rows)} unique jobs...", flush=True)
        for i, row in enumerate(rows):
            print(f"  [{i+1}/{len(rows)}] {row['url'][:80]}", flush=True)
            enrich_greenhouse_job(page, row)

        browser.close()

    # Filter low-quality rows
    rows_before_filter = len(rows)
    final_rows = [
        r for r in rows
        if r.get("url") and r.get("title") and r.get("company")
        and not re.match(r"^(Posted\b|Viewed\b|View job$|Applications$|Jobs$|Developers$)", r.get("title", ""), re.I)
        and is_relevant(r)
    ]
    filter_dropped = rows_before_filter - len(final_rows)

    print(f"  Profile filter dropped {filter_dropped} non-relevant jobs",
          flush=True)

    output_file.write_text(json.dumps(final_rows, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({
        "out": str(output_file),
        "count": len(final_rows),
        "dropped": len(rows) - len(final_rows),
        "countries": sorted({r.get("country", "") for r in final_rows}),
        "missing_descriptions": sum(1 for r in final_rows if not r.get("description")),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
