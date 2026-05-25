from __future__ import annotations

import sys
import urllib.parse
from pathlib import Path

from playwright.sync_api import sync_playwright

from scripts.pipeline.types import ShallowJob

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent

WELLFOUND_BASE = "https://wellfound.com"

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


def _set_role_filter(page, search_terms: list[str]) -> None:
    """Clear existing roles and add configured search terms to the role selector."""
    try:
        focus_btn = page.locator('[data-test="SearchBar-RoleSelect-FocusButton"]')
        if focus_btn.count() == 0:
            print("  [WARN] Role selector not found", file=sys.stderr, flush=True)
            return
        focus_btn.click()
        page.wait_for_timeout(500)

        # Clear existing pills
        removes = page.locator('.select__multi-value__remove')
        n = removes.count()
        for _ in range(n):
            page.locator('.select__multi-value__remove').first.click()
            page.wait_for_timeout(150)

        # Add each term
        rs = page.locator('input[id^="react-select"]').first
        for term in search_terms:
            page.locator('.select__control').first.click()
            page.wait_for_timeout(300)
            rs.fill(term)
            page.wait_for_timeout(800)
            opt = page.locator('.select__option').first
            if opt.count() > 0:
                opt.click()
            else:
                page.keyboard.press("Enter")
            page.wait_for_timeout(300)

        page.wait_for_timeout(1500)
        print(f"  Role filter set: {', '.join(search_terms)}", flush=True)
    except Exception as e:
        print(f"  [WARN] Role filter: {e}", file=sys.stderr, flush=True)


def wait_for_search_results(page, timeout: int = 30000) -> bool:
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


def _set_work_location_filter(page, work_style: str) -> None:
    label_map = {"remote": "Remote", "hybrid": "Hybrid", "onsite": "On-site"}
    target = label_map.get(work_style, "Remote")
    try:
        # "Remote only" button is a toggle — check text to see if already active
        btn = page.locator(
            'button:has-text("Remote"), button:has-text("On-site"), '
            'button:has-text("Onsite"), button:has-text("Hybrid"), '
            'button:has-text("Work Location")'
        ).first
        if btn.count() == 0:
            return
        btn_text = (btn.inner_text() or "").strip()
        # If it already says the target (e.g. "Remote only"), it's active — don't toggle off
        if target.lower() in btn_text.lower():
            print(f"  Work location filter already active: {btn_text!r}", flush=True)
            return
        btn.click()
        page.wait_for_timeout(800)
        opt = page.locator(f'[role="option"]:has-text("{target}")').first
        if opt.count() > 0:
            opt.click()
            page.wait_for_timeout(1500)
    except Exception as e:
        print(f"  [WARN] Work location filter: {e}", file=sys.stderr, flush=True)


def apply_filters(page, work_style: str = "remote", full_time: bool = True) -> bool:
    try:
        _set_work_location_filter(page, work_style)

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

        return True
    except Exception as e:
        print(f"  [WARN] Filter error: {e}", file=sys.stderr, flush=True)
        return False


def change_location(page, location_query: str) -> bool:
    """Check current location and log; Wellfound now uses saved searches for location."""
    try:
        current = page.evaluate("""() => {
            const btn = document.querySelector('button[aria-label="open menu"]');
            return btn ? btn.innerText.trim() : '';
        }""")
        if current and location_query.upper() in current.upper():
            print(f"  Location already {current!r} — no change needed", flush=True)
            return True
        print(f"  [INFO] Current location {current!r}, wanted {location_query!r} — using saved search", flush=True)
        return True
    except Exception as e:
        print(f"  [WARN] Location check failed: {e}", file=sys.stderr, flush=True)
        return True


def scroll_to_load_all(page, max_scrolls: int = 40) -> int:
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

            // Title lives in span[class*="title"] inside the job link
            const titleEl = link.querySelector('span[class*="title"]');
            const title = titleEl ? titleEl.innerText.trim() : '';

            // Company: walk up to data-test="StartupResult" card, grab h2 in company link
            let companyName = '';
            const card = link.closest('[data-test="StartupResult"]');
            if (card) {
                const compLink = card.querySelector('a[href*="/company/"] h2');
                companyName = compLink ? compLink.innerText.trim() : '';
            }

            // Location: direct children of the locations container (avoids duplicating parent text)
            const locContainer = link.querySelector('span[class*="locations"]');
            const locationEls = locContainer ? locContainer.querySelectorAll(':scope > span') : [];
            const locationText = Array.from(locationEls).map(el => el.innerText.trim()).filter(Boolean).join(', ');

            // Salary/equity from remaining link text
            const linkText = (link.innerText || '').trim();
            const salaryMatch = linkText.match(/[\\$€£][\\d,.]+[kK]?\\s*[–-]\\s*[\\$€£]?[\\d,.]+[kK]?/);
            const salaryText = salaryMatch ? salaryMatch[0] : '';
            const equityMatch = linkText.match(/[\\d.]+%\\s*[–-]\\s*[\\d.]+%/);
            const equityText = equityMatch ? equityMatch[0] : '';

            results.push({
                provider: 'wellfound',
                company: companyName,
                title: title,
                url: url,
                applyUrl: url,
                description: '',
                location: locationText,
                country: country,
                postingDate: '',
                salaryRaw: salaryText,
                equityRaw: equityText
            });
        });

        return results;
    }""",
        {"country": country, "baseUrl": WELLFOUND_BASE},
    )
    return rows


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
        seen: set[str] = set()
        wellfound_locations: list[str] = []
        for loc in configured_locations:
            continent = COUNTRY_TO_CONTINENT.get(loc.get("country_code", ""), "Europe")
            if continent not in seen:
                seen.add(continent)
                wellfound_locations.append(continent)
    else:
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
        page.bring_to_front()
        try:
            for wf_location in wellfound_locations:
                url_params: dict[str, str] = {}
                if remote:
                    url_params["remote"] = "true"
                nav_url = f"{WELLFOUND_BASE}/jobs?" + urllib.parse.urlencode(url_params) if url_params else f"{WELLFOUND_BASE}/jobs"
                page.goto(nav_url, wait_until="domcontentloaded", timeout=30000)
                page.wait_for_timeout(2000)

                _set_role_filter(page, search_terms)

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
            status="new",
        )
        jobs.append(j)

    if titles:
        jobs = [j for j in jobs if any(t.lower() in j.title.lower() for t in titles)]
    return jobs
