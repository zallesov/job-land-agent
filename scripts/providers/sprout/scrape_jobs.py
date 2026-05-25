from __future__ import annotations

import sqlite3
from pathlib import Path

from playwright.sync_api import sync_playwright

from scripts.pipeline.types import ShallowJob

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
        page.wait_for_timeout(100)
        title_input.fill("")
        page.wait_for_timeout(100)
        title_input.fill(title)
        page.wait_for_timeout(100)
        page.keyboard.press("Escape")
        page.wait_for_timeout(100)

        page.evaluate("""() => {
            const input = document.querySelector('input[placeholder*="Anywhere"], input[placeholder*="Location"]');
            if (input) input.focus();
        }""")
        page.wait_for_timeout(100)
        page.keyboard.press("Meta+a")
        page.keyboard.type(location, delay=50)
        page.wait_for_timeout(600)

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
        page.wait_for_timeout(200)

        page.locator('button:has-text("Search")').first.click()
        page.wait_for_timeout(1500)
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
        # Scroll the cards list container, not the window
        page.evaluate("""() => {
            const card = document.querySelector('[data-slot="card"]');
            if (card) {
                let el = card.parentElement;
                while (el && el !== document.body) {
                    const s = window.getComputedStyle(el);
                    if (s.overflowY === 'auto' || s.overflowY === 'scroll') {
                        el.scrollTop = el.scrollHeight;
                        return;
                    }
                    el = el.parentElement;
                }
            }
            window.scrollTo(0, document.body.scrollHeight);
        }""")
        page.wait_for_timeout(600)
    # Scroll back to top of the same container
    page.evaluate("""() => {
        const card = document.querySelector('[data-slot="card"]');
        if (card) {
            let el = card.parentElement;
            while (el && el !== document.body) {
                const s = window.getComputedStyle(el);
                if (s.overflowY === 'auto' || s.overflowY === 'scroll') {
                    el.scrollTop = 0;
                    return;
                }
                el = el.parentElement;
            }
        }
        window.scrollTo(0, 0);
    }""")
    page.wait_for_timeout(200)
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


def click_card_and_get_job_url(page, card_index: int) -> str | None:
    try:
        cards = page.locator('[data-slot="card"]')
        if cards.count() <= card_index:
            return None
        cards.nth(card_index).click()
        page.wait_for_timeout(300)

        # Try reading href directly from panel — no navigation needed
        direct_url = page.evaluate("""() => {
            for (const a of document.querySelectorAll('a[href]')) {
                const h = a.getAttribute('href');
                if (h && h.startsWith('http') &&
                    !h.includes('usesprout') && !h.includes('google') &&
                    !h.includes('stripe') && !h.includes('intercom')) {
                    return h;
                }
            }
            return null;
        }""")
        if direct_url:
            return direct_url

        # Intercept new tab from View Original — close immediately after URL grab
        try:
            with page.context.expect_page(timeout=3000) as new_page_info:
                page.evaluate("""() => {
                    for (const el of document.querySelectorAll('button, a')) {
                        if (el.innerText.includes('View Original')) { el.click(); return; }
                    }
                }""")
            new_page = new_page_info.value
            try:
                new_page.wait_for_load_state("domcontentloaded", timeout=5000)
            except Exception:
                pass
            job_url = new_page.url
            new_page.close()
            if job_url and "usesprout.com" not in job_url:
                return job_url
        except Exception:
            pass

        return None
    except Exception as e:
        print(f"    [WARN] Card {card_index}: {str(e)[:100]}", flush=True)
        return None


def collect_sprout(page, titles: list[str], location: str, country: str,
                   db_path: str | None = None) -> list[dict]:
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

            print(f"    [{len(all_jobs)+1}] {summary['company'][:20]} - {summary['title'][:50]}", flush=True)
            job_url = click_card_and_get_job_url(page, i)
            all_jobs.append({
                "provider": "sprout",
                "company": summary["company"],
                "title": summary["title"],
                "url": job_url or f"{SPROUT_BASE}/jobs?view=board",
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

    seen_dedup: set[str] = set()
    all_raw: list[dict] = []

    with sync_playwright() as pw:
        browser = pw.chromium.connect_over_cdp(cdp_url)
        ctx = browser.contexts[0]
        page = ctx.new_page()
        page.bring_to_front()
        try:
            page.goto(f"{SPROUT_BASE}/jobs?view=board", wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(500)
            for location in locations:
                rows = collect_sprout(
                    page,
                    titles=search_terms,
                    location=location["city"],
                    country=location["country"],
                    db_path=db_path,
                )
                for r in rows:
                    key = f"{r['company']}::{r['title']}"
                    if key not in seen_dedup:
                        seen_dedup.add(key)
                        all_raw.append(r)
        finally:
            page.close()

    jobs: list[ShallowJob] = []
    for r in all_raw:
        if not r.get("title") or not r.get("company"):
            continue
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
            status="new",
        )
        jobs.append(j)
    return jobs
