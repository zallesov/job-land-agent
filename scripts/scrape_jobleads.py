#!/usr/bin/env python3
"""
Scrape JobLeads job search results and save normalized JSON.

Usage:
  # Named location preset (personalized feed):
  python3 scripts/scrape_jobleads.py --location spain
  python3 scripts/scrape_jobleads.py --location berlin

  # Named location preset + job titles (keyword search per title):
  python3 scripts/scrape_jobleads.py --location berlin \
    --titles "Software Engineer" "AI Engineer" "Engineering Manager"

  # Custom search URL:
  python3 scripts/scrape_jobleads.py \
    --search-url "https://www.jobleads.com/search/jobs?..." \
    --country Spain --location-label "Spain"

Options:
  --location <name>       Named preset: berlin | spain
  --titles <str...>       Job titles (builds one search per title; without titles uses personalised feed)
  --search-url <url>      Raw search URL (can repeat; overrides --location + --titles)
  --country <str>         Country label for output JSON (used with --search-url)
  --location-label <str>  Label for output filename (used with --search-url)
  --output-dir <path>     Default: outputs/jobleads/runs/
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
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import quote_plus

from scripts.job_filter import is_relevant

JOBLEADS_BASE = "https://www.jobleads.com/search/jobs"

LOCATION_PRESETS: dict[str, dict] = {
    "spain": {
        "country": "Spain",
        "url_params": (
            "location_country=ES"
            "&filter_by_contractType=full_time"
            "&filter_by_remote=remote"
            "&minSalary=100000"
        ),
    },
    "berlin": {
        "country": "Germany",
        "url_params": (
            "location=Berlin%2C%20Germany"
            "&location_latitude=52.5173885"
            "&location_longitude=13.3951309"
            "&location_coordinates_radius=29495.470786527792"
            "&location_country=DE"
            "&filter_by_contractType=full_time"
            "&filter_by_remote=remote"
            "&minSalary=100000"
        ),
    },
}


def build_feed_url(preset: dict) -> str:
    return f"{JOBLEADS_BASE}?view=for-you&{preset['url_params']}"


def build_title_url(title: str, preset: dict) -> str:
    return f"{JOBLEADS_BASE}?q={quote_plus(title)}&{preset['url_params']}"

DEFAULT_PROFILE = Path.home() / ".interviews-browser-profile"
PROJECT_ROOT = Path(__file__).parent.parent


def slugify(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")


def is_auth_page(url: str) -> bool:
    return bool(re.search(r"/external-home|accounts\.google\.com|modal=login|sign.in", url))


def posting_date_from_relative(relative: str, today: str) -> str:
    if not relative:
        return ""
    base = date.fromisoformat(today)
    # Spanish: "Hace 12 días"
    m = re.match(r"Hace\s+(\d+)\s+d[ií]as?", relative, re.I)
    if m:
        return (base - timedelta(days=int(m.group(1)))).isoformat()
    # English: "12 days ago", "2 weeks ago", "1 month ago"
    m = re.match(r"(\d+)\s+(day|days)\s+ago", relative, re.I)
    if m:
        return (base - timedelta(days=int(m.group(1)))).isoformat()
    m = re.match(r"(\d+)\s+(week|weeks)\s+ago", relative, re.I)
    if m:
        return (base - timedelta(weeks=int(m.group(1)))).isoformat()
    m = re.match(r"(\d+)\s+(month|months)\s+ago", relative, re.I)
    if m:
        return (base - timedelta(days=int(m.group(1)) * 30)).isoformat()
    # German: "vor 5 Tagen", "vor 2 Wochen"
    m = re.match(r"vor\s+(\d+)\s+Tag", relative, re.I)
    if m:
        return (base - timedelta(days=int(m.group(1)))).isoformat()
    m = re.match(r"vor\s+(\d+)\s+Woch", relative, re.I)
    if m:
        return (base - timedelta(weeks=int(m.group(1)))).isoformat()
    return ""


def collect_jobleads(page, search: dict) -> list[dict]:
    page.goto(search["url"], wait_until="domcontentloaded", timeout=45000)
    page.wait_for_timeout(1500)

    if is_auth_page(page.url):
        print(f"\n⚠️  AUTH REQUIRED: JobLeads login needed for {search['label']}.",
              flush=True)
        print("Please log in to JobLeads in the Chrome browser window, then re-run.",
              flush=True)
        print("Exiting with code 10 to signal pipeline pause.", flush=True)
        raise SystemExit(10)

    # Wait for job cards
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


def enrich_jobleads_job(page, row: dict, today: str) -> None:
    row["postingDate"] = posting_date_from_relative(row.get("postedRelative", ""), today)
    try:
        page.goto(row["url"], wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(500)
        if not row.get("postingDate"):
            try:
                time_date = page.evaluate("""() => {
                    const t = document.querySelector('time[datetime]');
                    if (!t) return '';
                    const dt = t.getAttribute('datetime') || '';
                    const m = dt.match(/(\\d{4}-\\d{2}-\\d{2})/);
                    return m ? m[1] : '';
                }""")
                if time_date:
                    row["postingDate"] = time_date
            except Exception:
                pass
        description: str = page.evaluate(
            """() => {
            // DOM selectors first
            const descEl = document.querySelector('.job-description')
                        || document.querySelector('[class*="description"]')
                        || document.querySelector('[data-testid*="description"]')
                        || document.querySelector('article')
                        || document.querySelector('main');
            if (descEl) {
                const text = (descEl.innerText || '').trim();
                if (text.length > 100) return text.slice(0, 2000);
            }
            // Fallback: heading-based extraction
            const lines = (document.body.innerText || '').split('\\n').map(v => v.trim()).filter(Boolean);
            let description = '';
            for (let i = 0; i < lines.length; i++) {
                if (/^(Descripci[oó]n|Descripci[oó]n del puesto|Job description|About the job|About this role)$/i.test(lines[i])) {
                    description = lines.slice(i+1, i+25)
                        .filter(l => !/^(Solicitar|Aplicar|Guardar|Compartir|Trabajos similares|Vacantes similares)/i.test(l))
                        .join(' ');
                    break;
                }
            }
            if (!description || description.length < 80) {
                description = lines.filter(l => l.length > 80 && !/^https?:/.test(l)).slice(0, 8).join(' ');
            }
            return description.slice(0, 2000);
            }"""
        )
        if description:
            row["description"] = description
    except Exception as e:
        row["scrapeError"] = str(e)[:300]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--location", help="Named preset: berlin | spain")
    parser.add_argument("--titles", nargs="+", help="Job titles to search (one search per title)")
    parser.add_argument("--search-url", dest="search_urls", action="append",
                        metavar="URL", help="Raw search URL (can repeat)")
    parser.add_argument("--country", help="Country label (with --search-url)")
    parser.add_argument("--location-label", dest="location_label",
                        help="Location label for filename (with --search-url)")
    parser.add_argument("--output-dir", type=Path,
                        default=PROJECT_ROOT / "outputs" / "jobleads" / "runs")
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
                "country": args.country,
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
                    "country": preset["country"],
                    "url": build_title_url(title, preset),
                })
        else:
            searches.append({
                "label": f"{args.location.title()} Remote",
                "country": preset["country"],
                "url": build_feed_url(preset),
            })
    else:
        print("Provide --location <preset> or --search-url <url>", file=sys.stderr)
        return 2

    location_slug = slugify(args.location_label if args.search_urls else args.location)
    output_file = args.output_dir / f"jobleads_jobs_live_{args.date}_{location_slug}.json"
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
                cards = collect_jobleads(page, search)
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
            enrich_jobleads_job(page, row, args.date)

        browser.close()

    # Filter low-quality rows + sanity check
    rows_before_filter = len(rows)
    final_rows = [
        r for r in rows
        if r.get("url") and r.get("title") and r.get("company")
        and is_relevant(r)
    ]
    filter_dropped = rows_before_filter - len(final_rows)
    print(f"  Profile filter dropped {filter_dropped} non-relevant jobs", flush=True)

    output_file.write_text(json.dumps(final_rows, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({
        "out": str(output_file),
        "count": len(final_rows),
        "countries": sorted({r.get("country", "") for r in final_rows}),
        "missing_descriptions": sum(1 for r in final_rows if not r.get("description")),
        "missing_posting_dates": sum(1 for r in final_rows if not r.get("postingDate")),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
