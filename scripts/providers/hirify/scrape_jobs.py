from __future__ import annotations

import sys
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit

from playwright.sync_api import sync_playwright

from scripts.pipeline.types import ShallowJob
from scripts.providers.hirify.cdp_fallback import CdpPage
from scripts.providers._shared.job_filter import is_relevant

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
HIRIFY_BASE = "https://hirify.me"


def _load_config() -> dict:
    try:
        import yaml  # noqa: PLC0415
        p = PROJECT_ROOT / "config" / "user.yaml"
        return yaml.safe_load(p.read_text()) or {} if p.exists() else {}
    except Exception:
        return {}


def _canonical_url(url: str) -> str:
    absolute = urljoin(HIRIFY_BASE, (url or "").strip())
    parts = urlsplit(absolute)
    return urlunsplit((parts.scheme, parts.netloc, parts.path.rstrip("/"), "", ""))


def _normalize_raw_job(raw: dict) -> ShallowJob:
    title = (raw.get("title") or "").strip()
    company = (raw.get("company") or "").strip() or "Company hidden"
    url = _canonical_url(raw.get("url") or "")
    relevant = is_relevant({"title": title})
    return ShallowJob(
        provider="hirify",
        title=title,
        company=company,
        url=url,
        location=(raw.get("location") or "").strip(),
        country=(raw.get("country") or None),
        dedup_key=f"{company}::{title}",
        posting_date=None,
        salary_raw=(raw.get("salaryRaw") or None),
        status="listed" if relevant else "skip",
    )


def _get_saved_filters(page) -> list[dict]:
    filters = page.evaluate(
        """() => {
        const candidates = Array.from(document.querySelectorAll('button, a, [role="button"], [data-state], [class*="filter"], [class*="saved"]'));
        const visible = candidates.filter((el) => {
            const text = (el.innerText || el.textContent || '').trim();
            const rect = el.getBoundingClientRect();
            return text && rect.width > 0 && rect.height > 0;
        });
        const savedSection = visible.filter((el) => {
            const text = (el.innerText || el.textContent || '').trim().toLowerCase();
            const aria = (el.getAttribute('aria-label') || '').toLowerCase();
            const cls = (el.getAttribute('class') || '').toLowerCase();
            return aria.includes('filter') || aria.includes('saved') ||
                   cls.includes('filter') || cls.includes('saved') ||
                   text.includes('saved');
        });
        return savedSection.map((el, index) => ({
            index,
            label: (el.innerText || el.textContent || '').trim().replace(/\\s+/g, ' ').slice(0, 120),
        })).filter((item) => item.label && !/^show filters$/i.test(item.label) && !/^save filter$/i.test(item.label));
        }"""
    )
    return [f for f in filters if f.get("label")]


def _activate_saved_filter(page, saved_filter: dict) -> None:
    page.evaluate(
        """(index) => {
        const candidates = Array.from(document.querySelectorAll('button, a, [role="button"], [data-state], [class*="filter"], [class*="saved"]'));
        const visible = candidates.filter((el) => {
            const text = (el.innerText || el.textContent || '').trim();
            const rect = el.getBoundingClientRect();
            if (!text || rect.width <= 0 || rect.height <= 0) return false;
            if (/^(show filters|save filter)$/i.test(text)) return false;
            const aria = (el.getAttribute('aria-label') || '').toLowerCase();
            const cls = (el.getAttribute('class') || '').toLowerCase();
            const lowerText = text.toLowerCase();
            return aria.includes('filter') || aria.includes('saved') ||
                   cls.includes('filter') || cls.includes('saved') ||
                   lowerText.includes('saved');
        });
        const target = visible[index];
        if (!target) throw new Error(`Saved filter index not found: ${index}`);
        target.click();
        }""",
        saved_filter["index"],
    )
    page.wait_for_timeout(1500)


def _collect_current_page_jobs(page) -> list[dict]:
    return page.evaluate(
        """() => {
        const anchors = Array.from(document.querySelectorAll('a[href*="/jobs/"], a[href*="/job/"]'));
        const seen = new Set();
        function cardFor(anchor) {
            let node = anchor;
            let best = anchor;
            while (node && node !== document.body) {
                const text = (node.innerText || '').trim();
                if (text.length > 40 && text.length < 1600) best = node;
                node = node.parentElement;
            }
            return best;
        }
        return anchors.map((anchor) => {
            const url = new URL(anchor.getAttribute('href'), window.location.href).href;
            if (seen.has(url)) return null;
            seen.add(url);
            const card = cardFor(anchor);
            const lines = (card.innerText || '').split('\\n').map((v) => v.trim()).filter(Boolean);
            const anchorText = (anchor.innerText || '').trim();
            const title = anchorText || lines.find((line) => line.length > 3) || '';
            const salary = lines.find((line) => /([$€₽]|USD|EUR|RUB|GBP|USDT)/i.test(line)) || '';
            const company = lines.find((line) => line !== title && !/seconds ago|minutes ago|updated|fulltime|parttime|remote|hybrid|onsite/i.test(line)) || '';
            const locationParts = lines.filter((line) => /remote|hybrid|onsite|Europe|USA|Germany|Spain|UK|Poland|Lithuania|France|Italy|Serbia|Japan|Russia/i.test(line));
            const country = (locationParts.join(' ').match(/Germany|Spain|UK|Poland|Lithuania|France|Italy|Serbia|Japan|Russia|USA|Europe/i) || [''])[0];
            return {
                title,
                company,
                url,
                location: locationParts.join(' '),
                country,
                salaryRaw: salary,
            };
        }).filter((row) => row && row.title && row.url);
        }"""
    )


def _page_signature(rows: list[dict]) -> tuple[str, ...]:
    return tuple(sorted(_canonical_url(row.get("url") or "") for row in rows if row.get("url")))


def _click_next_page(page) -> bool:
    return bool(page.evaluate(
        """() => {
        const candidates = Array.from(document.querySelectorAll('a, button'));
        const next = candidates.find((el) => /^next$/i.test((el.innerText || el.textContent || '').trim()));
        if (!next) return false;
        const disabled = next.disabled || next.getAttribute('aria-disabled') === 'true' || /disabled/i.test(next.getAttribute('class') || '');
        if (disabled) return false;
        next.click();
        return true;
        }"""
    ))


def _scrape_filter_pages(page) -> list[dict]:
    rows: list[dict] = []
    seen_page_signatures: set[tuple[str, ...]] = set()
    for _ in range(100):
        page.wait_for_timeout(1000)
        current = _collect_current_page_jobs(page)
        signature = _page_signature(current)
        if not signature or signature in seen_page_signatures:
            break
        seen_page_signatures.add(signature)
        rows.extend(current)
        if not _click_next_page(page):
            break
    return rows


def scrape_jobs(
    cdp_url: str,
    titles: list[str] | None = None,
    db_path: str | None = None,
    _config: dict | None = None,
) -> list[ShallowJob]:
    _ = titles, db_path, (_config if _config is not None else _load_config())
    try:
        return _scrape_jobs_with_playwright(cdp_url)
    except Exception as e:
        if "Browser.setDownloadBehavior" not in str(e):
            raise
        return _scrape_jobs_with_cdp(cdp_url)


def _scrape_jobs_from_page(page) -> list[ShallowJob]:
    raw_rows: list[dict] = []
    seen_urls: set[str] = set()

    page.goto(HIRIFY_BASE, wait_until="domcontentloaded", timeout=30000)
    page.wait_for_timeout(2000)
    filters = _get_saved_filters(page)
    if not filters:
        print(
            "[hirify] No saved filters found. Create saved filters on https://hirify.me/ first.",
            file=sys.stderr,
            flush=True,
        )
        return []
    for saved_filter in filters:
        try:
            _activate_saved_filter(page, saved_filter)
            for row in _scrape_filter_pages(page):
                url = _canonical_url(row.get("url") or "")
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    row["url"] = url
                    raw_rows.append(row)
        except Exception as e:
            print(
                f"[hirify] WARNING: saved filter {saved_filter.get('label', saved_filter.get('index'))!r} failed: {e}",
                file=sys.stderr,
                flush=True,
            )

    jobs: list[ShallowJob] = []
    for row in raw_rows:
        if not row.get("title") or not row.get("url"):
            continue
        jobs.append(_normalize_raw_job(row))
    return jobs


def _scrape_jobs_with_playwright(cdp_url: str) -> list[ShallowJob]:
    with sync_playwright() as pw:
        browser = pw.chromium.connect_over_cdp(cdp_url)
        ctx = browser.contexts[0]
        page = ctx.new_page()
        try:
            return _scrape_jobs_from_page(page)
        finally:
            page.close()


def _scrape_jobs_with_cdp(cdp_url: str) -> list[ShallowJob]:
    page = CdpPage(cdp_url)
    try:
        return _scrape_jobs_from_page(page)
    finally:
        page.close()
