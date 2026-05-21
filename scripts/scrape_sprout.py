#!/usr/bin/env python3
"""
Scrape Sprout job board via CDP connection to existing Chrome.

Sprout (usesprout.com) is an AI job search platform that aggregates listings
from ATS systems (Ashby, Greenhouse, Lever, etc.). Jobs are displayed in a
board view at /jobs?view=board. Each card opens a detail panel; the "View
Original" button navigates to the source ATS listing.

Usage:
  python3 scripts/scrape_sprout.py
  python3 scripts/scrape_sprout.py --titles "Software Engineer" "AI Engineer" "Engineering Manager"

Options:
  --titles <str...>       Job titles to search (one search per title)
  --cdp-url <url>         CDP endpoint (default: http://localhost:9222)
  --date <YYYY-MM-DD>     Override today's date in output filename
  --max-jobs <N>          Limit total jobs across all searches (0 = all)
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

LOCATION_PRESETS: dict[str, str] = {
    "berlin": "Berlin",
    "spain": "Spain",
}

SPROUT_BASE = "https://app.usesprout.com"
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


def set_work_location_filter(page, preferred: str) -> None:
    """Set Work Location filter in Sprout UI from config work_style.preferred.

    Opens the Filters dropdown, expands Work Location, and sets the
    appropriate checkbox (Remote/Hybrid/In Person). Also unchecks
    'Include unknown work location' to get only exact matches.
    """
    mapping = {"remote": "Remote", "hybrid": "Hybrid", "onsite": "In Person"}
    label = mapping.get(preferred.lower(), "Remote")

    try:
        # Open Filters dropdown
        btn = page.locator(
            'button[data-slot="dropdown-menu-trigger"]:has-text("Filters")'
        ).first
        if btn.count() == 0:
            print("  [WARN] Filters button not found — skipping work location filter",
                  flush=True)
            return
        btn.click()
        page.wait_for_timeout(800)

        # Expand Work Location section (may already be expanded)
        wl = page.locator('[role="menuitem"]:has-text("Work Location")').first
        if wl.count() > 0:
            expanded = wl.get_attribute("aria-expanded") or wl.get_attribute(
                "data-state"
            )
            if expanded != "true":
                wl.click()
                page.wait_for_timeout(500)

        # Set the correct checkbox, unset the others
        for opt_text in ["Remote", "Hybrid", "In Person"]:
            cb = page.locator(
                f'[role="menuitemcheckbox"]:has-text("{opt_text}")'
            ).first
            if cb.count() == 0:
                continue
            checked = cb.get_attribute("aria-checked") or cb.get_attribute(
                "data-state"
            )
            should_be = (opt_text == label)
            if (checked == "true") != should_be:
                cb.click()
                page.wait_for_timeout(300)

        # Uncheck "Include unknown work location"
        unknown = page.locator(
            '[role="menuitemcheckbox"]:has-text("Include unknown work location")'
        ).first
        if unknown.count() > 0:
            checked = unknown.get_attribute("aria-checked") or unknown.get_attribute(
                "data-state"
            )
            if checked == "true":
                unknown.click()
                page.wait_for_timeout(300)

        # Close dropdown
        page.keyboard.press("Escape")
        page.wait_for_timeout(500)
        print(f"    Work Location → {label!r}", flush=True)

    except Exception as e:
        print(f"  [WARN] set_work_location_filter: {e}", flush=True)
        try:
            page.keyboard.press("Escape")
        except Exception:
            pass


def search_jobs(page, title: str, location: str) -> bool:
    """Type title + location, select autocomplete, and search."""
    return _search_via_inputs(page, title, location)


def _search_via_inputs(page, title: str, location: str) -> bool:
    """Type title + location, select autocomplete via JS, click Search."""
    try:
        # Title input
        title_input = page.locator('input[placeholder*="Job"]').first
        if title_input.count() == 0:
            title_input = page.locator('input').first
        title_input.click()
        page.wait_for_timeout(300)
        title_input.fill("")
        page.wait_for_timeout(200)
        title_input.fill(title)
        page.wait_for_timeout(300)
        page.keyboard.press("Escape")
        page.wait_for_timeout(300)

        # Location input — click via JS to avoid chip overlay, select-all to clear, then type
        page.evaluate("""() => {
            const input = document.querySelector('input[placeholder*="Anywhere"], input[placeholder*="Location"]');
            if (input) input.focus();
        }""")
        page.wait_for_timeout(300)
        page.keyboard.press("Meta+a")   # select all existing text
        page.keyboard.type(location, delay=50)
        page.wait_for_timeout(2000)  # Wait for autocomplete dropdown

        # Dropdown options are in a portal — use JS to find and click first match
        clicked = page.evaluate(f"""(loc) => {{
            const opts = document.querySelectorAll('[role="option"]');
            for (const o of opts) {{
                if (o.innerText.toLowerCase().includes('{location.lower()}')) {{
                    o.click();
                    return o.innerText;
                }}
            }}
            return null;
        }}""")
        if clicked:
            print(f"    Location set to: {clicked}", flush=True)
        page.wait_for_timeout(500)

        page.locator('button:has-text("Search")').first.click()
        page.wait_for_timeout(4000)
        return True
    except Exception as e:
        print(f"  [WARN] Input search failed: {e}", file=sys.stderr, flush=True)
        return False


def scroll_to_load_all(page, max_scrolls: int = 20) -> int:
    """Scroll to trigger lazy loading. Returns total cards found."""
    last_count = 0
    no_new_count = 0

    for i in range(max_scrolls):
        current_count = page.evaluate(
            "() => document.querySelectorAll('[data-slot=\"card\"]').length"
        )
        print(f"    Scroll {i+1}: {current_count} cards visible", flush=True)

        if current_count == last_count:
            no_new_count += 1
            if no_new_count >= 3:
                print("    No new cards, stopping scroll.", flush=True)
                break
        else:
            no_new_count = 0
            last_count = current_count

        page.evaluate("() => window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(2000)

    page.evaluate("() => window.scrollTo(0, 0)")
    page.wait_for_timeout(500)
    return last_count


def collect_card_summaries(page) -> list[dict]:
    """Collect company+title from ALL visible cards (after scrolling)."""
    return page.evaluate("""() => {
        const cards = document.querySelectorAll('[data-slot="card"]');
        const results = [];
        cards.forEach(card => {
            const text = card.innerText || '';
            const lines = text.split('\\n').map(l => l.trim()).filter(Boolean);
            const title = lines[0] || '';
            const company = lines[1] || '';
            const location = lines.find(l => /berlin|spain|remote|germany|everywhere|london|new york/i.test(l)) || '';
            const date = lines.find(l => /posted|day|week|month|ago/i.test(l)) || '';
            const salary = lines.find(l => /[\\$€£]\\s*\\d/.test(l) || /\\d+k/i.test(l)) || '';
            if (title && company && title !== company) {
                results.push({title, company, location, date, salary});
            }
        });
        return results;
    }""")


def open_card_and_get_url(page, card_index: int) -> str | None:
    """Click a card, extract original URL from page state or View Original button."""
    try:
        cards = page.locator('[data-slot="card"]')
        if cards.count() <= card_index:
            return None

        cards.nth(card_index).click()
        page.wait_for_timeout(2000)

        # Try to extract original URL from the detail panel via JS
        url = page.evaluate("""() => {
            // Look for any element containing an external URL
            const links = document.querySelectorAll('a[href]');
            for (const a of links) {
                const h = a.getAttribute('href');
                if (h && !h.includes('usesprout') && !h.includes('google') &&
                    !h.includes('stripe') && !h.includes('intercom') &&
                    h.startsWith('http')) {
                    return h;
                }
            }
            // Try buttons with onclick that navigate
            const buttons = document.querySelectorAll('button');
            for (const b of buttons) {
                const text = b.innerText || '';
                if (text.includes('View Original') || text.includes('Apply')) {
                    const onclick = b.getAttribute('onclick') || '';
                    const match = onclick.match(/(https?:\\/\\/[^\\s"']+)/);
                    if (match) return match[1];
                }
            }
            return null;
        }""")

        if url and "usesprout.com" not in url:
            return url

        # Try clicking View Original and capturing via all methods
        vo_btn = page.locator('button:has-text("View Original")').first
        if vo_btn.count() == 0:
            vo_btn = page.locator('a:has-text("View Original")').first
        if vo_btn.count() == 0:
            return None

        # Use JS click to trigger React handler
        page.evaluate("""() => {
            const buttons = document.querySelectorAll('button');
            for (const b of buttons) {
                if (b.innerText.includes('View Original')) {
                    b.click();
                    return true;
                }
            }
            return false;
        }""")

        context = page.context
        pages_before = {p.url for p in context.pages}
        original_url = page.url

        # Method 1: wait for new page (JS click already triggered above)
        try:
            page.wait_for_timeout(2000)
            for p in context.pages:
                if p.url not in pages_before and "usesprout.com" not in p.url:
                    url = p.url
                    try:
                        p.close()
                    except Exception:
                        pass
                    return url
        except Exception:
            pass

        # Method 2: URL change in current page
        page.wait_for_timeout(1000)
        if page.url != original_url and "usesprout.com" not in page.url:
            url = page.url
            page.go_back(wait_until="domcontentloaded", timeout=10000)
            page.wait_for_timeout(2000)
            return url

        return None

    except Exception as e:
        print(f"    [WARN] Card {card_index}: {str(e)[:100]}", file=sys.stderr, flush=True)
        return None


def _known_dedup_keys(db_path: str) -> set[str]:
    """Return all dedup_keys already in the DB."""
    try:
        import sqlite3  # noqa: PLC0415
        con = sqlite3.connect(db_path)
        try:
            return {row[0] for row in con.execute("SELECT dedup_key FROM jobs").fetchall()}
        finally:
            con.close()
    except Exception:
        return set()


def collect_sprout(page, titles: list[str], location: str, country: str, max_jobs: int = 0,
                   db_path: str | None = None) -> list[dict]:
    """Run searches and collect jobs with dedup by original URL."""
    seen_urls: set[str] = set()
    all_jobs: list[dict] = []

    known_keys = _known_dedup_keys(db_path) if db_path else set()
    if known_keys:
        print(f"  [dedup] {len(known_keys)} jobs already in DB — will skip matching cards", flush=True)

    # Clean up stale pages from previous runs
    context = page.context
    for p in list(context.pages):
        if p != page and "usesprout.com" not in p.url:
            try:
                p.close()
            except Exception:
                pass

    for title in titles:
        print(f"  Searching: {title} in {location}", flush=True)
        search_jobs(page, title, location)

        # Scroll to load all results
        scroll_to_load_all(page)

        # Collect card summaries
        summaries = collect_card_summaries(page)
        print(f"    {len(summaries)} cards visible", flush=True)

        if not summaries:
            continue

        # For each card, get original URL
        for i, summary in enumerate(summaries):
            if max_jobs and len(all_jobs) >= max_jobs:
                break

            # Quick dedup by company+title within same search
            dup_key = f"{summary['company']}|{summary['title']}"
            if any(j.get("_dup_key") == dup_key for j in all_jobs):
                continue

            # Skip cards already in DB — no need to open the page
            db_key = f"{summary['company']}::{summary['title']}"
            if db_key in known_keys:
                print(f"    [skip] {summary['company'][:20]} - {summary['title'][:50]} (in DB)", flush=True)
                continue

            print(f"    [{len(all_jobs)+1}] {summary['company'][:20]} - {summary['title'][:50]}", flush=True)
            original_url = open_card_and_get_url(page, i)

            if original_url and original_url in seen_urls:
                print(f"      [DUP] same as existing, skipping", flush=True)
                # Close the duplicate page
                for p in context.pages:
                    if p.url == original_url:
                        try:
                            p.close()
                        except Exception:
                            pass
                        break
                continue

            if original_url:
                seen_urls.add(original_url)

            all_jobs.append({
                "provider": "sprout",
                "company": summary["company"],
                "title": summary["title"],
                "url": original_url or f"{SPROUT_BASE}/jobs?view=board",
                "applyUrl": original_url or "",
                "description": "",
                "location": summary.get("location", ""),
                "country": country,
                "postingDate": summary.get("date", ""),
                "salaryRaw": "",
                "equityRaw": "",
                "_dup_key": dup_key,
            })

        if max_jobs and len(all_jobs) >= max_jobs:
            break

    # Clean up internal keys
    for job in all_jobs:
        job.pop("_dup_key", None)

    return all_jobs


def enrich_sprout_job(page, row: dict) -> None:
    try:
        url = row.get("url", "")
        if not url or "usesprout.com" in url:
            return
        page.goto(url, wait_until="domcontentloaded", timeout=15000)
        page.wait_for_timeout(500)
        details = page.evaluate(
            """() => {
            const lines = (document.body.innerText || '').split('\\n').map(v => v.trim()).filter(Boolean);

            // Description: prefer known containers, else heuristic
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

            // Salary
            const salaryRaw = lines.find(l =>
                /\\d/.test(l) && /[\\$€£]|USD|EUR|GBP|salary|compensation/i.test(l) &&
                !/cookie|privacy|terms|sign in|copyright/i.test(l)
            ) || '';

            // Posting date: <time datetime> first, then "posted X days ago" pattern
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
                    else {
                        const rel = dateLine.match(/(\\d+)\\s*(day|week|month)/i);
                        if (rel) postingDate = dateLine.slice(0, 60);
                    }
                }
            }

            return { description, salaryRaw, postingDate };
            }"""
        )
        if details.get("description"):
            row["description"] = details["description"]
        if details.get("salaryRaw"):
            row["salaryRaw"] = details["salaryRaw"]
        if details.get("postingDate"):
            row["postingDate"] = details["postingDate"]
    except Exception as e:
        print(f"  [WARN] enrich_sprout_job failed for {row.get('url', '')[:80]}: {e}", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--titles", nargs="+", help="Override: job titles to search")
    parser.add_argument("--cdp-url", default="http://localhost:9222")
    parser.add_argument("--output-dir", type=Path,
                        default=PROJECT_ROOT / "outputs" / "sprout" / "runs")
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--max-jobs", type=int, default=0)
    args = parser.parse_args()

    cfg = load_config()
    titles: list[str] = args.titles or cfg.get("search_terms", [])
    work_style = cfg.get("work_style", {})
    preferred_work_type = work_style.get("preferred", "remote")

    location_keys = config_location_keys(cfg)
    if not location_keys:
        print("No locations in config/user.yaml. Add locations with country_code DE or ES.",
              file=sys.stderr)
        return 2

    args.output_dir.mkdir(parents=True, exist_ok=True)
    print(f"CDP: {args.cdp_url}", flush=True)
    print(f"Locations: {location_keys}", flush=True)
    print(f"Titles: {titles}", flush=True)

    from playwright.sync_api import sync_playwright  # noqa: PLC0415

    with sync_playwright() as pw:
        browser = pw.chromium.connect_over_cdp(args.cdp_url)
        context = browser.contexts[0]

        for location_key in location_keys:
            if location_key not in LOCATION_PRESETS:
                print(f"  [SKIP] Unknown preset {location_key!r}", file=sys.stderr, flush=True)
                continue

            location_str = LOCATION_PRESETS[location_key]
            location_slug = slugify(location_key)
            output_file = args.output_dir / f"sprout_jobs_live_{args.date}_{location_slug}.json"
            print(f"\n=== {location_key.upper()} -> {location_str} ===", flush=True)
            print(f"Output: {output_file}", flush=True)

            # Clean up stale pages from previous location
            for p in list(context.pages):
                if "usesprout.com" not in p.url:
                    try:
                        p.close()
                    except Exception:
                        pass

            page = context.new_page()

            # Navigate to board view
            print("Loading board view...", flush=True)
            page.goto(f"{SPROUT_BASE}/jobs?view=board", wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(4000)

            if "sign-in" in page.url or "auth" in page.url:
                print(f"\n⚠️  AUTH REQUIRED: Sprout login needed.", flush=True)
                print("Exiting with code 10 to signal pipeline pause.", flush=True)
                browser.close()
                raise SystemExit(10)

            # Set work location filter from config (Remote/Hybrid/On-site)
            set_work_location_filter(page, preferred_work_type)

            db = str(PROJECT_ROOT / "jobs.db")
            jobs = collect_sprout(page, titles, location_str, location_key.title(), args.max_jobs, db_path=db)
            print(f"Enriching {len(jobs)} jobs...", flush=True)
            for i, row in enumerate(jobs):
                print(f"  [{i+1}/{len(jobs)}] {row['url'][:80]}", flush=True)
                enrich_sprout_job(page, row)

            page.close()

            # Filter and save
            rows_before = len(jobs)
            final = [
                j for j in jobs
                if j.get("url") and j.get("title") and j.get("company")
                and is_relevant(j)
            ]
            print(f"  Profile filter dropped {rows_before - len(final)} non-relevant jobs", flush=True)
            output_file.write_text(json.dumps(final, indent=2, ensure_ascii=False) + "\n")
            print(json.dumps({
                "out": str(output_file), "count": len(final),
                "dropped": rows_before - len(final),
            }, indent=2), flush=True)

        browser.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
