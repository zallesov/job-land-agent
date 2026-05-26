from __future__ import annotations

from pathlib import Path

from scripts.db import get_connection, update_job_status
from .types import HermesResult

_DEFAULT_DB = str(Path(__file__).parent.parent.parent / "jobs.db")
_DEFAULT_CDP = "http://localhost:9222"
hermes_call = None


def _extract_page(page) -> dict:
    return page.evaluate("""() => {
        const h1 = document.querySelector('h1');
        const title = h1 ? h1.innerText.trim() : document.title.split('|')[0].trim();

        let description = '';
        const selectors = [
            '[class*="description"]', '[id*="description"]',
            '[class*="job-detail"]', '[class*="content"]',
            'article', 'main'
        ];
        for (const sel of selectors) {
            const el = document.querySelector(sel);
            if (el && (el.innerText || '').length > 200) {
                description = el.innerText.trim().slice(0, 3000);
                break;
            }
        }
        if (!description) {
            const parts = [];
            document.querySelectorAll('p, li').forEach(el => {
                const t = (el.innerText || '').trim();
                if (t.length > 50) parts.push(t);
            });
            description = parts.join('\\n').slice(0, 3000);
        }

        const bodyText = document.body.innerText || '';
        const salaryMatch = bodyText.match(
            /[$€£][\\d,.]+[kK]?\\s*[-–]\\s*[$€£]?[\\d,.]+[kK]?\\s*(USD|EUR|GBP|per year|annually)?/i
        );
        const salaryRaw = salaryMatch ? salaryMatch[0].trim() : '';

        let applyUrl = window.location.href;
        const applyAnchor = Array.from(document.querySelectorAll('a[href]'))
            .find(a => /apply/i.test(a.innerText || '') && a.href);
        if (applyAnchor) applyUrl = applyAnchor.href;

        let datePosted = '';
        const timeEl = document.querySelector('time[datetime]');
        if (timeEl) {
            const m = (timeEl.getAttribute('datetime') || '').match(/(\\d{4}-\\d{2}-\\d{2})/);
            if (m) datePosted = m[1];
        }

        return { title, description, applyUrl, salaryRaw, datePosted };
    }""")


def enrich_job(
    job_id: int,
    db_path: str = _DEFAULT_DB,
    cdp_url: str = _DEFAULT_CDP,
) -> HermesResult:
    con = get_connection(db_path)
    try:
        job = con.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        if job is None:
            return HermesResult(success=False, data={}, error=f"job {job_id} not found", raw_output="")

        url = job["url"]
        context = {
            "job_id": job_id,
            "url": url,
            "cv_path": str(Path(__file__).parent.parent.parent / "config" / "cv.md"),
        }

        if callable(hermes_call):
            result = hermes_call("enrich-job", context)
            if not result.success:
                update_job_status(con, job_id, "enrich_failed", comment=result.error)
                con.commit()
                return result
            data = result.data
        else:
            try:
                from playwright.sync_api import sync_playwright  # noqa: PLC0415
                with sync_playwright() as pw:
                    browser = pw.chromium.connect_over_cdp(cdp_url)
                    ctx = browser.contexts[0]
                    page = ctx.new_page()
                    page.bring_to_front()
                    try:
                        page.goto(url, wait_until="domcontentloaded", timeout=20000)
                        try:
                            page.wait_for_selector("h1", timeout=8000)
                        except Exception:
                            pass
                        page.wait_for_timeout(500)
                        data = _extract_page(page)
                    finally:
                        page.close()
            except Exception as e:
                err = str(e)[:300]
                update_job_status(con, job_id, "enrich_failed", comment=err)
                con.commit()
                return HermesResult(success=False, data={}, error=err, raw_output="")

        description = data.get("description") or ""
        title = data.get("title") or None
        apply_url = data.get("applyUrl") or data.get("apply_url") or None
        salary_range = data.get("salaryRaw") or data.get("salary_range") or None
        date_posted = data.get("datePosted") or data.get("date_posted") or None

        if not callable(hermes_call) and (not description or len(description) < 100):
            err = "extraction failed: description too short"
            update_job_status(con, job_id, "enrich_failed", comment=err)
            con.commit()
            return HermesResult(success=False, data={}, error=err, raw_output="")

        con.execute(
            """UPDATE jobs SET title = COALESCE(?, title),
               description = ?, apply_url = ?,
               salary_range = COALESCE(?, salary_range),
               date_posted = COALESCE(?, date_posted),
               status = 'new', updated_at = datetime('now')
               WHERE id = ?""",
            (title, description, apply_url, salary_range, date_posted, job_id),
        )
        con.commit()
        return HermesResult(success=True, data=data, error=None, raw_output="")
    finally:
        con.close()
