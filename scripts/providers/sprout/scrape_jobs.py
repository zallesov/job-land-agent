from __future__ import annotations

import sqlite3
from pathlib import Path

from playwright.sync_api import sync_playwright

from scripts.pipeline.types import ShallowJob
from scripts.providers._shared.job_filter import is_relevant

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent

SPROUT_BASE = "https://app.usesprout.com"

DEFAULT_TITLES = [
    "Software Engineer", "Backend Engineer", "AI Engineer",
    "Platform Engineer", "Engineering Manager",
]


def _load_config() -> dict:
    try:
        import yaml  # noqa: PLC0415
        p = PROJECT_ROOT / "config" / "user.yaml"
        return yaml.safe_load(p.read_text()) or {} if p.exists() else {}
    except Exception:
        return {}


def _known_dedup_keys(db_path: str) -> set[str]:
    try:
        con = sqlite3.connect(db_path)
        try:
            return {row[0] for row in con.execute(
                "SELECT dedup_key FROM jobs WHERE dedup_key IS NOT NULL"
            ).fetchall()}
        finally:
            con.close()
    except Exception:
        return set()


def search_jobs(page, title: str, location: str) -> bool:
    try:
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

        page.evaluate("""() => {
            const input = document.querySelector('input[placeholder*="Anywhere"], input[placeholder*="Location"]');
            if (input) input.focus();
        }""")
        page.wait_for_timeout(300)
        page.keyboard.press("Meta+a")
        page.keyboard.type(location, delay=50)
        page.wait_for_timeout(2000)

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
        print(f"  [WARN] search_jobs failed: {e}", flush=True)
        return False


def scroll_to_load_all(page, max_scrolls: int = 20) -> int:
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
    try:
        cards = page.locator('[data-slot="card"]')
        if cards.count() <= card_index:
            return None

        cards.nth(card_index).click()
        page.wait_for_timeout(2000)

        url = page.evaluate("""() => {
            const links = document.querySelectorAll('a[href]');
            for (const a of links) {
                const h = a.getAttribute('href');
                if (h && !h.includes('usesprout') && !h.includes('google') &&
                    !h.includes('stripe') && !h.includes('intercom') &&
                    h.startsWith('http')) {
                    return h;
                }
            }
            return null;
        }""")

        if url and "usesprout.com" not in url:
            return url

        vo_btn = page.locator('button:has-text("View Original")').first
        if vo_btn.count() == 0:
            vo_btn = page.locator('a:has-text("View Original")').first
        if vo_btn.count() == 0:
            return None

        page.evaluate("""() => {
            const buttons = document.querySelectorAll('button');
            for (const b of buttons) {
                if (b.innerText.includes('View Original')) { b.click(); return true; }
            }
            return false;
        }""")

        context = page.context
        pages_before = {p.url for p in context.pages}
        original_url = page.url

        page.wait_for_timeout(2000)
        for p in context.pages:
            if p.url not in pages_before and "usesprout.com" not in p.url:
                found = p.url
                try:
                    p.close()
                except Exception:
                    pass
                return found

        page.wait_for_timeout(1000)
        if page.url != original_url and "usesprout.com" not in page.url:
            found = page.url
            page.go_back(wait_until="domcontentloaded", timeout=10000)
            page.wait_for_timeout(2000)
            return found

        return None
    except Exception as e:
        print(f"    [WARN] Card {card_index}: {str(e)[:100]}", flush=True)
        return None


def collect_sprout(page, titles: list[str], location: str, country: str,
                   db_path: str | None = None) -> list[dict]:
    seen_urls: set[str] = set()
    all_jobs: list[dict] = []

    known_keys = _known_dedup_keys(db_path) if db_path else set()
    if known_keys:
        print(f"  [dedup] {len(known_keys)} jobs already in DB", flush=True)

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
        scroll_to_load_all(page)
        summaries = collect_card_summaries(page)
        print(f"    {len(summaries)} cards visible", flush=True)

        if not summaries:
            continue

        for i, summary in enumerate(summaries):
            dup_key = f"{summary['company']}|{summary['title']}"
            if any(j.get("_dup_key") == dup_key for j in all_jobs):
                continue

            db_key = f"{summary['company']}::{summary['title']}"
            if db_key in known_keys:
                print(f"    [skip] {summary['company'][:20]} - {summary['title'][:50]} (in DB)", flush=True)
                continue

            if not is_relevant({"title": summary["title"]}):
                all_jobs.append({
                    "provider": "sprout",
                    "company": summary["company"],
                    "title": summary["title"],
                    "url": f"urn:skip:sprout:{summary['company']}::{summary['title']}",
                    "location": summary.get("location", ""),
                    "country": country,
                    "_skip": True,
                    "_dup_key": dup_key,
                })
                continue

            print(f"    [{len(all_jobs)+1}] {summary['company'][:20]} - {summary['title'][:50]}", flush=True)
            original_url = open_card_and_get_url(page, i)

            if original_url and original_url in seen_urls:
                continue
            if original_url:
                seen_urls.add(original_url)

            all_jobs.append({
                "provider": "sprout",
                "company": summary["company"],
                "title": summary["title"],
                "url": original_url or f"{SPROUT_BASE}/jobs?view=board",
                "location": summary.get("location", ""),
                "country": country,
                "postingDate": summary.get("date", ""),
                "salaryRaw": "",
                "_dup_key": dup_key,
            })

    for job in all_jobs:
        job.pop("_dup_key", None)
    return all_jobs


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
    search_terms = titles or cfg.get("search_terms") or DEFAULT_TITLES

    seen_urls: set[str] = set()
    all_raw: list[dict] = []

    with sync_playwright() as pw:
        browser = pw.chromium.connect_over_cdp(cdp_url)
        ctx = browser.contexts[0]
        page = ctx.new_page()
        try:
            page.goto(f"{SPROUT_BASE}/jobs?view=board", wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(2000)
            for location in locations:
                rows = collect_sprout(
                    page,
                    titles=search_terms,
                    location=location["city"],
                    country=location["country"],
                    db_path=db_path,
                )
                for r in rows:
                    if r.get("url") and r["url"] not in seen_urls:
                        seen_urls.add(r["url"])
                        all_raw.append(r)
        finally:
            page.close()

    jobs: list[ShallowJob] = []
    for r in all_raw:
        if not r.get("title") or not r.get("company"):
            continue
        relevant = is_relevant({"title": r["title"]})
        j = ShallowJob(
            provider="sprout",
            title=r["title"],
            company=r["company"],
            url=r["url"],
            location=r.get("location", ""),
            country=r.get("country") or "",
            dedup_key=f"{r['company']}::{r['title']}",
            posting_date=None,
            salary_raw=r.get("salaryRaw") or None,
            status="new" if relevant else "skip",
        )
        jobs.append(j)
    return jobs
