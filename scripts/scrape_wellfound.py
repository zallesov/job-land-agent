#!/usr/bin/env python3
"""
Scrape WellFound job search results via CDP connection to existing Chrome.

Connects to the already-running Chrome at localhost:9222 (same instance used by
the Hermes browser tools). No new browser launch — uses the existing authenticated
session, avoiding Playwright detection and profile lock conflicts.

Strategy:
  1. Connect to Chrome via CDP (connect_over_cdp)
  2. Navigate to /jobs — saved search loads automatically
  3. Apply filters: Remote Only, $100k+ salary, Full Time
  4. Change location via UI interaction
  5. Scroll to load all results via infinite scroll
  6. Collect job cards from DOM
  7. Enrich each job by visiting its detail page

Usage:
  python3 scripts/scrape_wellfound.py --location berlin
  python3 scripts/scrape_wellfound.py --location berlin --skip-enrich --max-jobs 10

Options:
  --location <name>       Named preset: berlin | spain
  --cdp-url <url>         CDP endpoint (default: http://localhost:9222)
  --date <YYYY-MM-DD>     Override today's date in output filename
  --skip-enrich           Skip detail page enrichment (faster)
  --max-jobs <N>          Limit number of jobs to scrape (0 = all)
  --remote-only           Filter to remote-only jobs (default: True)
  --min-salary <N>        Minimum salary in USD (default: 100000)
  --full-time             Filter to full-time only (default: True)
  --no-filters            Skip filter application entirely
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import date
from pathlib import Path

from scripts.job_filter import is_relevant

# ---------------------------------------------------------------------------
# Location presets
# ---------------------------------------------------------------------------
LOCATION_PRESETS: dict[str, str] = {
    "berlin": "Berlin, Germany",
    "spain": "Spain",
}

WELLFOUND_BASE = "https://wellfound.com"
PROJECT_ROOT = Path(__file__).parent.parent


def slugify(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")


def wait_for_search_results(page, timeout: int = 30000) -> bool:
    """Wait for job search results to appear on the page."""
    try:
        page.wait_for_selector('a[href*="/company/"]', timeout=timeout)
        return True
    except Exception:
        pass
    try:
        page.wait_for_selector('a[href*="/jobs/"]', timeout=5000)
        return True
    except Exception:
        return False


def apply_filters(page, remote_only: bool = True, full_time: bool = True) -> bool:
    """Apply Remote Only and Full Time filters via simple UI toggles.
    
    STRATEGY: Use the toggle buttons visible in the search bar (NOT the Filters
    modal — opening it resets the saved search SPA state). WellFound shows:
    - "Full Time" as a toggle button in the search bar
    - Remote/On-site as a button next to location
    
    For salary $100k+: use URL param ?salary_min=100000 which WellFound respects.
    """
    try:
        print("  Applying filters...", flush=True)
        
        # ── Remote Only ──
        if remote_only:
            remote_applied = False
            try:
                # Look for the remote toggle button near the search bar
                remote_btns = page.locator(
                    'button:has-text("Remote"), '
                    'button:has-text("On-site"), '
                    'button:has-text("Onsite")'
                )
                if remote_btns.count() > 0:
                    first_btn = remote_btns.first
                    if first_btn.is_enabled():
                        first_btn.click()
                        page.wait_for_timeout(800)
                        remote_opt = page.locator(
                            '[role="option"]:has-text("Remote"), '
                            'text="Remote only", '
                            'label:has-text("Remote")'
                        ).first
                        if remote_opt.count() > 0:
                            remote_opt.click()
                            page.wait_for_timeout(1500)
                            print("  ✓ Remote Only selected via UI", flush=True)
                            remote_applied = True
            except Exception as e:
                print(f"  [INFO] Remote UI toggle failed: {e}", flush=True)
            
            if not remote_applied:
                print("  [INFO] Remote toggle disabled/missing, using URL param", flush=True)
                current_url = page.url.split("?")[0]
                page.goto(current_url + "?remote=true", 
                          wait_until="domcontentloaded", timeout=15000)
                page.wait_for_timeout(3000)
                print("  ✓ Remote Only via URL", flush=True)
        
        # ── Full Time toggle ──
        if full_time:
            ft_btn = page.locator('button:has-text("Full Time")').first
            if ft_btn.count() > 0:
                try:
                    btn_text = ft_btn.inner_text()
                except Exception:
                    btn_text = ""
                if "Clear" not in btn_text:
                    ft_btn.click()
                    page.wait_for_timeout(1500)
                    print("  ✓ Full Time toggled ON", flush=True)
                else:
                    print("  ✓ Full Time already ON", flush=True)
        
        # ── Salary minimum via URL ──
        # WellFound supports ?salary_min=100000 as URL parameter
        current_url = page.url
        if "salary_min=" not in current_url:
            sep = "&" if "?" in current_url else "?"
            page.goto(current_url + f"{sep}salary_min=100000", 
                      wait_until="domcontentloaded", timeout=15000)
            page.wait_for_timeout(3000)
            print("  ✓ Salary min $100k via URL param", flush=True)
        
        print("  ✓ All filters applied", flush=True)
        return True
        
    except Exception as e:
        print(f"  [WARN] Filter application error: {e}", file=sys.stderr, flush=True)
        return False


def change_location(page, location_query: str) -> bool:
    """Change the location filter by interacting with the SPA UI.
    
    Current WellFound UI (May 2026): The location is a button with a map-pin
    icon showing the current city, next to a combobox for region (e.g. "Europe").
    Clicking the location button opens a search input for city selection.
    """
    try:
        # Approach 1: Click the location button (has map pin img)
        # The button shows something like "Berlin" with a pin icon
        loc_btn = page.locator('button:has(img[alt*="@"])').first
        if loc_btn.count() > 0:
            loc_btn.click()
            page.wait_for_timeout(1000)
        else:
            # Approach 2: Click any element showing the current city name
            page.locator('text="Berlin"').first.click()
            page.wait_for_timeout(1000)

        # A location search input should appear
        loc_input = page.locator(
            'input[placeholder*="Location"], '
            'input[aria-label*="location" i], '
            'input[aria-label*="Location"]'
        ).first
        
        if loc_input.count() == 0:
            # Try the combobox approach
            cb_btn = page.locator('button:has-text("Europe"), button:has-text("Worldwide")').first
            if cb_btn.count() > 0:
                cb_btn.click()
                page.wait_for_timeout(500)
            loc_input = page.locator('[role="combobox"] input').first
        
        if loc_input.count() > 0:
            loc_input.click()
            page.wait_for_timeout(300)
            loc_input.fill("")
            page.wait_for_timeout(200)
            loc_input.type(location_query, delay=50)
            page.wait_for_timeout(1500)

            # Select first suggestion from dropdown
            suggestions = page.locator('[role="option"]')
            if suggestions.count() > 0:
                suggestions.first.click()
                page.wait_for_timeout(2000)
                return wait_for_search_results(page)
        
        # If no input found, the saved search may already have the right location
        print("  [INFO] Location input not found — using saved search location", flush=True)
        return True

    except Exception as e:
        print(f"  [WARN] Could not change location: {e}", file=sys.stderr, flush=True)
        print("  [INFO] Continuing with existing location filter", flush=True)

    return False


def scroll_to_load_all(page, max_scrolls: int = 40) -> int:
    """Scroll to trigger infinite scroll. Returns total job links found."""
    last_count = 0
    no_new_count = 0
    final_count = 0

    for i in range(max_scrolls):
        current_count = page.evaluate(
            "() => document.querySelectorAll('a[href*=\"/jobs/\"]').length"
        )
        print(f"  Scroll {i+1}: {current_count} job links visible", flush=True)
        final_count = current_count

        if current_count == last_count:
            no_new_count += 1
            if no_new_count >= 4:
                print("  No new content after 4 scrolls, stopping.", flush=True)
                break
        else:
            no_new_count = 0
            last_count = current_count

        page.evaluate("() => window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(1500)

    page.evaluate("() => window.scrollTo(0, 0)")
    page.wait_for_timeout(500)
    return final_count


def collect_wellfound(page, country: str) -> list[dict]:
    """Extract job cards from the search results DOM."""
    rows: list[dict] = page.evaluate(
        """(args) => {
        const { country, baseUrl } = args;
        const jobLinks = document.querySelectorAll('a[href*="/jobs/"]');
        const seen = new Set();
        const results = [];

        jobLinks.forEach(link => {
            const href = link.getAttribute('href') || '';
            if (!/^\\/jobs\\/\\d+/.test(href)) return;

            const url = new URL(href, baseUrl).href.split('#')[0];
            if (seen.has(url)) return;
            seen.add(url);

            const linkText = (link.innerText || '').trim();
            const lines = linkText.split('\\n').map(l => l.trim()).filter(Boolean);

            const title = lines[0] || '';
            const locationText = lines.find(l =>
                /remote|onsite|hybrid|berlin|germany|spain|espa|everywhere|europe/i.test(l) &&
                !/posted|week|day|month|ago|salary|equity|\\$/i.test(l)
            ) || '';
            const salaryText = lines.find(l => /[\\$€£]/.test(l) && /\\d/.test(l)) || '';
            const equityText = lines.find(l => /%/.test(l) && /\\d/.test(l)) || '';
            const dateText = lines.find(l => /posted|week|day|month|ago/i.test(l)) || '';

            // Find company name by walking up the DOM
            let companyName = '';
            let el = link.closest('div[class]');
            for (let i = 0; i < 6 && el; i++) {
                const heading = el.querySelector('h2, h3');
                if (heading) {
                    const hText = (heading.innerText || '').trim();
                    if (hText && hText.length < 100 && !hText.includes('\\n') && !/search|results|jobs/i.test(hText)) {
                        companyName = hText;
                        break;
                    }
                }
                const cLink = el.querySelector('a[href*="/company/"]');
                if (cLink) {
                    const cText = (cLink.innerText || '').trim().split('\\n')[0];
                    if (cText && cText.length < 80 && !/logo/i.test(cText)) {
                        companyName = cText;
                        break;
                    }
                }
                el = el.parentElement;
            }

            results.push({
                provider: 'wellfound',
                company: companyName,
                title: title,
                url: url,
                applyUrl: url,
                description: '',
                location: locationText,
                country: country,
                postingDate: dateText,
                salaryRaw: salaryText,
                equityRaw: equityText
            });
        });

        return results;
    }""",
        {"country": country, "baseUrl": WELLFOUND_BASE},
    )
    return rows


def enrich_wellfound_job(page, row: dict) -> None:
    """Visit job detail page and extract full description + metadata."""
    try:
        page.goto(row["url"], wait_until="domcontentloaded", timeout=15000)
        page.wait_for_timeout(1000)

        details = page.evaluate(
            """() => {
            const body = (document.body.innerText || '');
            const lines = body.split('\\n').map(l => l.trim()).filter(Boolean);

            // Title
            const h1 = document.querySelector('h1');
            const title = h1 ? h1.innerText.trim() : '';

            // Company from breadcrumb links
            const companyLinks = document.querySelectorAll('a[href*="/company/"]');
            let company = '';
            companyLinks.forEach(a => {
                const text = a.innerText.trim();
                if (text && text.length < 80 && !text.includes('logo') && !text.includes('company logo')) {
                    company = company || text;
                }
            });

            // Description — try structured selectors first
            let description = '';
            const descSelectors = ['[class*="description"]', '[class*="content"]', 'article', 'main'];
            for (const sel of descSelectors) {
                const el = document.querySelector(sel);
                if (el && el.innerText.length > 200) {
                    description = el.innerText.trim().slice(0, 3000);
                    break;
                }
            }
            if (!description) {
                const paragraphs = document.querySelectorAll('p, li');
                const parts = [];
                paragraphs.forEach(p => {
                    const t = p.innerText.trim();
                    if (t.length > 40) parts.push(t);
                });
                description = parts.join('\\n').slice(0, 3000);
            }

            // Metadata from definition list (dt/dd pairs)
            let location = '', remotePolicy = '', salaryRaw = '';
            const skills = [];
            const dts = document.querySelectorAll('dt');
            dts.forEach(dt => {
                const label = dt.innerText.trim().toLowerCase();
                const dd = dt.nextElementSibling;
                const value = dd ? dd.innerText.trim() : '';
                if (label.includes('location')) location = location || value;
                if (label.includes('remote')) remotePolicy = value;
                if (label.includes('salary') || label.includes('compensation')) salaryRaw = value;
                if (label.includes('skill')) {
                    const tags = dd ? dd.querySelectorAll('[class*="tag"], [class*="skill"], span') : [];
                    tags.forEach(t => skills.push(t.innerText.trim()));
                    if (!skills.length && value) {
                        skills.push(...value.split(/[,;]/).map(s => s.trim()).filter(Boolean));
                    }
                }
            });
            if (!location) {
                location = lines.find(l =>
                    /remote|onsite|hybrid|berlin|germany|spain|barcelona|everywhere|europe/i.test(l) &&
                    !/posted|apply|save|share/i.test(l)
                ) || '';
            }

            // Skills from sidebar tags
            const allTagEls = document.querySelectorAll('[class*="skill"], [class*="tag"]');
            const allSkills = skills.slice();
            allTagEls.forEach(s => {
                const t = s.innerText.trim();
                if (t && t.length < 40 && !allSkills.includes(t)) allSkills.push(t);
            });

            // External apply link
            let applyUrl = window.location.href;
            const extApply = Array.from(document.querySelectorAll('a')).find(a => {
                const h = a.getAttribute('href') || '';
                return h && !h.includes('wellfound.com') && /apply|career|job/i.test(h);
            });
            if (extApply) applyUrl = extApply.getAttribute('href');

            return {
                title, company, description, location, remotePolicy,
                salaryRaw, skills: allSkills, applyUrl
            };
        }"""
        )

        if details.get("title"):
            row["title"] = details["title"]
        if details.get("company"):
            row["company"] = details["company"]
        if details.get("description"):
            row["description"] = details["description"]
        if details.get("location"):
            row["location"] = details["location"]
        if details.get("applyUrl") and details["applyUrl"] != row["url"]:
            row["applyUrl"] = details["applyUrl"]
        if details.get("salaryRaw"):
            row["salaryRaw"] = details["salaryRaw"]
        if details.get("skills"):
            row["skills"] = details["skills"]

    except Exception as e:
        row["scrapeError"] = str(e)[:300]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--location", help="Named preset: berlin | spain")
    parser.add_argument("--cdp-url", default="http://localhost:9222",
                        help="CDP endpoint (default: http://localhost:9222)")
    parser.add_argument("--output-dir", type=Path,
                        default=PROJECT_ROOT / "outputs" / "wellfound" / "runs")
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--skip-enrich", action="store_true",
                        help="Skip detail page enrichment (faster)")
    parser.add_argument("--max-jobs", type=int, default=0,
                        help="Limit number of jobs (0 = all)")
    parser.add_argument("--remote-only", action="store_true", default=True,
                        help="Filter to remote-only jobs (default: True)")
    parser.add_argument("--min-salary", type=int, default=100000,
                        help="Minimum salary in USD (default: 100000)")
    parser.add_argument("--full-time", action="store_true", default=True,
                        help="Filter to full-time only (default: True)")
    parser.add_argument("--no-filters", action="store_true",
                        help="Skip filter application entirely")
    args = parser.parse_args()

    if not args.location or args.location.lower() not in LOCATION_PRESETS:
        print(f"Unknown location: {args.location!r}. Known: {list(LOCATION_PRESETS)}",
              file=sys.stderr)
        return 2

    preset = LOCATION_PRESETS[args.location.lower()]
    location_slug = slugify(args.location)
    output_file = args.output_dir / f"wellfound_jobs_live_{args.date}_{location_slug}.json"
    args.output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Location: {args.location} -> {preset}", flush=True)
    print(f"CDP: {args.cdp_url}", flush=True)
    print(f"Filters: remote={args.remote_only} salary>={args.min_salary} fulltime={args.full_time}", flush=True)
    print(f"Output: {output_file}", flush=True)

    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        # Connect to existing Chrome via CDP — no new browser launch
        print("Connecting to existing Chrome via CDP...", flush=True)
        try:
            browser = pw.chromium.connect_over_cdp(args.cdp_url)
        except Exception as e:
            print(f"ERROR: Could not connect to Chrome at {args.cdp_url}: {e}",
                  file=sys.stderr)
            print("Make sure Chrome is running with --remote-debugging-port=9222",
                  file=sys.stderr)
            return 1

        # Use the default context (already authenticated)
        contexts = browser.contexts
        if not contexts:
            print("ERROR: No browser contexts found", file=sys.stderr)
            return 1

        context = contexts[0]
        # Create a fresh page for clean navigation
        page = context.new_page()

        # ── Phase 1: Load search results ──
        print("Navigating to /jobs...", flush=True)
        page.goto(f"{WELLFOUND_BASE}/jobs", wait_until="domcontentloaded", timeout=45000)
        page.wait_for_timeout(4000)

        if not wait_for_search_results(page, timeout=15000):
            print("  Initial wait failed, retrying...", flush=True)
            page.wait_for_timeout(5000)
            if not wait_for_search_results(page, timeout=15000):
                # Check if we hit an auth page
                if "sign_in" in page.url.lower() or "login" in page.url.lower() or "auth" in page.url.lower():
                    print(f"\n⚠️  AUTH REQUIRED: WellFound login needed.",
                          flush=True)
                    print("Please log in to WellFound in the Chrome browser window, then re-run.",
                          flush=True)
                    print("Exiting with code 10 to signal pipeline pause.", flush=True)
                    raise SystemExit(10)
                print("ERROR: No search results loaded. Is WellFound logged in?",
                      file=sys.stderr)
                browser.close()
                return 1

        # ── Phase 2: Apply filters ──
        if not args.no_filters:
            apply_filters(page, remote_only=args.remote_only, full_time=args.full_time)
            page.wait_for_timeout(2000)

        # ── Phase 3: Change location ──
        print(f"Setting location to: {preset}", flush=True)
        change_location(page, preset)
        page.wait_for_timeout(2000)

        # ── Phase 4: Scroll to load all ──
        print("Loading all results via scroll...", flush=True)
        total = scroll_to_load_all(page)

        # ── Phase 5: Collect cards ──
        print("Collecting job cards...", flush=True)
        rows = collect_wellfound(page, args.location.title())
        print(f"  Found {len(rows)} unique job cards (from {total} links)", flush=True)

        if args.max_jobs and args.max_jobs < len(rows):
            rows = rows[: args.max_jobs]
            print(f"  Limited to {len(rows)} jobs", flush=True)

        # ── Phase 6: Enrich ──
        if not args.skip_enrich and rows:
            print(f"Enriching {len(rows)} jobs from detail pages...", flush=True)
            for i, row in enumerate(rows):
                print(f"  [{i+1}/{len(rows)}] {row['title'][:80]}", flush=True)
                enrich_wellfound_job(page, row)
        elif args.skip_enrich:
            print("Skipping enrichment (--skip-enrich)", flush=True)

        browser.close()

    # ── Phase 7: Filter and save ──
    rows_before_filter = len(rows)
    final_rows = [
        r for r in rows
        if r.get("url") and r.get("title") and r.get("company")
        and not re.match(
            r"^(Posted\b|Viewed\b|View job$|Applications$|Jobs$)",
            r.get("title", ""), re.I
        )
        and is_relevant(r)
    ]
    filter_dropped = rows_before_filter - len(final_rows)
    print(f"  Profile filter dropped {filter_dropped} non-relevant jobs", flush=True)

    output_file.write_text(json.dumps(final_rows, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({
        "out": str(output_file),
        "count": len(final_rows),
        "dropped": len(rows) - len(final_rows),
        "missing_descriptions": sum(1 for r in final_rows if not r.get("description")),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
