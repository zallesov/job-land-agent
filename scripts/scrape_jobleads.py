#!/usr/bin/env python3
"""
Scrape JobLeads job search results and save normalized JSON.

Usage:
  # Named location preset (personalized feed):
  python3 scripts/scrape_jobleads.py

  # Named location preset + job titles (keyword search per title):
  python3 scripts/scrape_jobleads.py \
    --titles "Software Engineer" "AI Engineer" "Engineering Manager"

  # Custom search URL:
  python3 scripts/scrape_jobleads.py \
    --search-url "https://www.jobleads.com/search/jobs?..." \
    --country Spain --location-label "Spain"

Options:
  --titles <str...>       Job titles (builds one search per title; without titles uses personalised feed)
  --search-url <url>      Raw search URL (can repeat; overrides --location + --titles)
  --country <str>         Country label for output JSON (used with --search-url)
  --location-label <str>  Label for output filename (used with --search-url)
  --output-dir <path>     Default: outputs/jobleads/runs/
  --browser-profile <p>   Persistent Chromium profile dir (default: ~/.chrome-profile)
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

sys.path.insert(0, str(Path(__file__).parent.parent))

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

DEFAULT_PROFILE = Path.home() / ".chrome-profile"
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


def build_feed_url(preset: dict) -> str:
    return f"{JOBLEADS_BASE}?view=for-you&{preset['url_params']}"


def build_title_url(title: str, preset: dict) -> str:
    return f"{JOBLEADS_BASE}?q={quote_plus(title)}&{preset['url_params']}"


def slugify(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")


def is_auth_page(url: str) -> bool:
    return bool(re.search(r"/external-home|accounts\.google\.com|modal=login|sign.in", url))


def is_unauthenticated(page) -> bool:
    """Check page content for signals that the session is not logged in."""
    try:
        body = (page.content() or "").lower()
        return "solo para miembros registrados" in body
    except Exception:
        return False


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

    if is_unauthenticated(page):
        print(f"\n⚠️  AUTH REQUIRED: JobLeads session not authenticated (anonymous mode detected) for {search['label']}.",
              flush=True)
        print("Company names hidden as 'Solo para miembros registrados' — login needed.",
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
    parser.add_argument("--titles", nargs="+", help="Override: job titles to search")
    parser.add_argument("--search-url", dest="search_urls", action="append",
                        metavar="URL", help="Raw search URL (can repeat; overrides all other options)")
    parser.add_argument("--country", help="Country label (with --search-url)")
    parser.add_argument("--location-label", dest="location_label",
                        help="Location label for filename (with --search-url)")
    parser.add_argument("--output-dir", type=Path,
                        default=PROJECT_ROOT / "outputs" / "jobleads" / "runs")
    parser.add_argument("--browser-profile", type=Path, default=DEFAULT_PROFILE,
                        help="[DEPRECATED] ignored — CDP uses existing Chrome")
    parser.add_argument("--cdp-url", default="http://localhost:9222")
    parser.add_argument("--headless", action="store_true", help="[DEPRECATED] ignored")
    parser.add_argument("--date", default=date.today().isoformat())
    args = parser.parse_args()

    cfg = load_config()
    titles: list[str] = args.titles or cfg.get("search_terms", [])

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
                {"label": f"{args.country} - {args.location_label}",
                 "country": args.country, "url": url}
                for url in args.search_urls
            ]
            location_slug = slugify(args.location_label)
            output_file = args.output_dir / f"jobleads_jobs_live_{args.date}_{location_slug}.json"
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
            output_file = args.output_dir / f"jobleads_jobs_live_{args.date}_{location_slug}.json"

            if titles:
                searches = [
                    {"label": f"{t} - {location_key.title()} Remote",
                     "country": preset["country"], "url": build_title_url(t, preset)}
                    for t in titles
                ]
            else:
                searches = [
                    {"label": f"{location_key.title()} Remote",
                     "country": preset["country"], "url": build_feed_url(preset)}
                ]

            print(f"\n=== {location_key.upper()} — {len(searches)} search(es) ===", flush=True)
            _run_location(page, searches, output_file, args.date)

        browser.close()
    return 0


def _run_location(page, searches: list[dict], output_file: Path, today: str) -> None:
    """Run all searches for one location, enrich, filter, and write file."""
    import re  # noqa: PLC0415
    rows_by_url: dict[str, dict] = {}
    for search in searches:
        print(f"  Scraping: {search['label']}", flush=True)
        try:
            cards = collect_jobleads(page, search)
            print(f"    Found {len(cards)} cards", flush=True)
            for card in cards:
                rows_by_url.setdefault(card["url"], card)
        except SystemExit:
            raise
        except Exception as e:
            print(f"    ERROR: {e}", file=sys.stderr, flush=True)

    rows = list(rows_by_url.values())

    relevant_rows = [r for r in rows if r.get("url") and r.get("title") and r.get("company") and is_relevant(r)]
    skip_rows = [r for r in rows if r.get("title") and r.get("company") and r not in relevant_rows]
    print(f"  Profile filter: {len(relevant_rows)} relevant, {len(skip_rows)} skipped", flush=True)

    print(f"Enriching {len(relevant_rows)} relevant jobs...", flush=True)
    for i, row in enumerate(relevant_rows):
        print(f"  [{i+1}/{len(relevant_rows)}] {row['url'][:80]}", flush=True)
        enrich_jobleads_job(page, row, today)

    for row in skip_rows:
        row["_skip"] = True

    all_rows = relevant_rows + skip_rows
    output_file.write_text(json.dumps(all_rows, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({
        "out": str(output_file), "count": len(relevant_rows), "skipped": len(skip_rows),
        "countries": sorted({r.get("country", "") for r in relevant_rows}),
        "missing_descriptions": sum(1 for r in relevant_rows if not r.get("description")),
        "missing_posting_dates": sum(1 for r in relevant_rows if not r.get("postingDate")),
    }, indent=2), flush=True)


if __name__ == "__main__":
    raise SystemExit(main())
