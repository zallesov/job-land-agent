# Hirify Saved Filters Provider Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Hirify as a first-class provider that scrapes all jobs from all saved filters configured by the user on `https://hirify.me/`.

**Architecture:** Hirify follows the existing provider contract under `scripts/providers/hirify/`. The provider uses the shared Chrome CDP session, enumerates saved filters in the Hirify UI, paginates each filter's results, normalizes rows to `ShallowJob`, and lets the existing pipeline dedup/enrich/ingest flow handle the rest.

**Tech Stack:** Python 3.11, Playwright sync API, pytest, Next.js/TypeScript dashboard.

---

## File Map

- Create `scripts/providers/hirify/__init__.py`: package marker.
- Create `scripts/providers/hirify/check_auth.py`: CDP auth check for Hirify.
- Create `scripts/providers/hirify/scrape_jobs.py`: Hirify saved-filter scraper and pure parsing helpers.
- Create `tests/providers/hirify/__init__.py`: test package marker.
- Create `tests/providers/hirify/test_scrape_jobs.py`: unit tests for parsing, pagination behavior, saved-filter iteration, dedup, and title handling.
- Modify `tests/test_scraping_pipeline.py`: assert `hirify` is accepted by provider registry/CLI choices.
- Modify `tests/providers/test_check_auth.py`: add optional e2e Hirify auth check.
- Modify `scripts/scraping_pipeline.py`: add `hirify` to provider set and help text.
- Modify `scripts/consolidate_provider_run.py`: add `hirify` to choices.
- Modify `config/user.yaml.example`: add `providers.hirify`.
- Modify `skills/onboarding/SKILL.md`: add Hirify to user-facing provider list and generated config.
- Modify `skills/run-scraping-pipeline/SKILL.md`: add Hirify trigger/docs.
- Modify `README.md`: add Hirify to supported boards and scraping description.
- Modify `dashboard/app/components/JobList.tsx`: add Hirify provider color. `JobDetail.tsx` imports this map, so no separate map is needed.
- Review `config/scraping-workflow.yaml`: add Hirify only where the workflow enumerates provider IDs for scrape steps.

---

### Task 1: Register Hirify In Pipeline Choices

**Files:**
- Modify: `scripts/scraping_pipeline.py`
- Modify: `scripts/consolidate_provider_run.py`
- Test: `tests/test_scraping_pipeline.py`

- [ ] **Step 1: Write the failing registry test**

Add this test near the bottom of `tests/test_scraping_pipeline.py`:

```python
def test_hirify_is_registered_provider():
    from scripts.scraping_pipeline import PROVIDERS

    assert "hirify" in PROVIDERS
```

- [ ] **Step 2: Run the test and verify it fails**

Run:

```bash
pytest tests/test_scraping_pipeline.py::test_hirify_is_registered_provider -v
```

Expected: `FAIL` because `"hirify"` is not in `PROVIDERS`.

- [ ] **Step 3: Add Hirify to pipeline provider set**

In `scripts/scraping_pipeline.py`, update the usage docstring provider list and provider set:

```python
Options:
  --provider <name>   Provider: greenhouse | jobleads | wellfound | sprout | hirify
```

```python
PROVIDERS = {"greenhouse", "jobleads", "wellfound", "sprout", "hirify"}
```

- [ ] **Step 4: Add Hirify to consolidate choices**

In `scripts/consolidate_provider_run.py`, update the choices list:

```python
parser.add_argument(
    "--provider",
    required=True,
    choices=["greenhouse", "jobleads", "wellfound", "sprout", "hirify"],
)
```

- [ ] **Step 5: Run the registry test and related pipeline tests**

Run:

```bash
pytest tests/test_scraping_pipeline.py::test_hirify_is_registered_provider tests/test_scraping_pipeline.py::test_titles_passed_to_scrape_jobs -v
```

Expected: both tests pass.

- [ ] **Step 6: Commit**

Run:

```bash
git add scripts/scraping_pipeline.py scripts/consolidate_provider_run.py tests/test_scraping_pipeline.py
git commit -m "feat: register hirify provider"
```

---

### Task 2: Add Pure Hirify Parsing And Normalization Helpers

**Files:**
- Create: `scripts/providers/hirify/__init__.py`
- Create: `scripts/providers/hirify/scrape_jobs.py`
- Test: `tests/providers/hirify/__init__.py`
- Test: `tests/providers/hirify/test_scrape_jobs.py`

- [ ] **Step 1: Create failing tests for pure helpers**

Create `tests/providers/hirify/__init__.py` as an empty file.

Create `tests/providers/hirify/test_scrape_jobs.py` with:

```python
from scripts.providers.hirify.scrape_jobs import (
    HIRIFY_BASE,
    _canonical_url,
    _normalize_raw_job,
)


def test_canonical_url_resolves_relative_hirify_links():
    assert _canonical_url("/jobs/123-ai-engineer") == "https://hirify.me/jobs/123-ai-engineer"


def test_normalize_raw_job_maps_required_fields():
    raw = {
        "title": "Senior AI Engineer",
        "company": "Acme",
        "url": "/jobs/123-ai-engineer?utm_source=x",
        "location": "remote Germany fulltime senior",
        "country": "Germany",
        "salaryRaw": "100 000 - 130 000 €",
    }

    job = _normalize_raw_job(raw)

    assert job.provider == "hirify"
    assert job.title == "Senior AI Engineer"
    assert job.company == "Acme"
    assert job.url == f"{HIRIFY_BASE}/jobs/123-ai-engineer"
    assert job.location == "remote Germany fulltime senior"
    assert job.country == "Germany"
    assert job.dedup_key == "Acme::Senior AI Engineer"
    assert job.salary_raw == "100 000 - 130 000 €"
    assert job.posting_date is None
    assert job.status == "listed"


def test_normalize_raw_job_uses_company_hidden_fallback():
    job = _normalize_raw_job({
        "title": "Backend Engineer",
        "company": "",
        "url": "https://hirify.me/jobs/456-backend",
    })

    assert job.company == "Company hidden"
    assert job.dedup_key == "Company hidden::Backend Engineer"
```

- [ ] **Step 2: Run the helper tests and verify they fail**

Run:

```bash
pytest tests/providers/hirify/test_scrape_jobs.py -v
```

Expected: import failure because `scripts.providers.hirify.scrape_jobs` does not exist.

- [ ] **Step 3: Create provider package and helper implementation**

Create `scripts/providers/hirify/__init__.py` as an empty file.

Create `scripts/providers/hirify/scrape_jobs.py` with the imports, constants, and helpers:

```python
from __future__ import annotations

import sys
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit

from playwright.sync_api import sync_playwright

from scripts.pipeline.types import ShallowJob
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
```

- [ ] **Step 4: Run helper tests**

Run:

```bash
pytest tests/providers/hirify/test_scrape_jobs.py -v
```

Expected: all helper tests pass.

- [ ] **Step 5: Commit**

Run:

```bash
git add scripts/providers/hirify tests/providers/hirify
git commit -m "feat: add hirify parsing helpers"
```

---

### Task 3: Implement Saved Filter And Card Collection Helpers

**Files:**
- Modify: `scripts/providers/hirify/scrape_jobs.py`
- Test: `tests/providers/hirify/test_scrape_jobs.py`

- [ ] **Step 1: Add tests for saved-filter and card helper delegation**

Append these tests:

```python
from unittest.mock import MagicMock, patch


def test_get_saved_filters_extracts_labels_and_indexes():
    from scripts.providers.hirify import scrape_jobs as mod

    page = MagicMock()
    page.evaluate.return_value = [
        {"index": 0, "label": "AI Remote"},
        {"index": 1, "label": "Backend Europe"},
    ]

    filters = mod._get_saved_filters(page)

    assert filters == [
        {"index": 0, "label": "AI Remote"},
        {"index": 1, "label": "Backend Europe"},
    ]
    assert "saved" in page.evaluate.call_args[0][0].lower()


def test_collect_current_page_jobs_returns_raw_rows():
    from scripts.providers.hirify import scrape_jobs as mod

    page = MagicMock()
    page.evaluate.return_value = [{
        "title": "AI Engineer",
        "company": "Acme",
        "url": "https://hirify.me/jobs/1",
        "location": "remote Germany",
        "country": "Germany",
        "salaryRaw": "100 000 €",
    }]

    rows = mod._collect_current_page_jobs(page)

    assert rows[0]["title"] == "AI Engineer"
    assert rows[0]["url"] == "https://hirify.me/jobs/1"
```

- [ ] **Step 2: Run the new tests and verify they fail**

Run:

```bash
pytest tests/providers/hirify/test_scrape_jobs.py::test_get_saved_filters_extracts_labels_and_indexes tests/providers/hirify/test_scrape_jobs.py::test_collect_current_page_jobs_returns_raw_rows -v
```

Expected: `AttributeError` for missing helper functions.

- [ ] **Step 3: Implement `_get_saved_filters`, `_activate_saved_filter`, and `_collect_current_page_jobs`**

Append these functions to `scripts/providers/hirify/scrape_jobs.py`:

```python
def _get_saved_filters(page) -> list[dict]:
    filters = page.evaluate(
        """() => {
        const candidates = Array.from(document.querySelectorAll('button, a, [role="button"], [data-state], [class*="filter"]'));
        const visible = candidates.filter((el) => {
            const text = (el.innerText || el.textContent || '').trim();
            const rect = el.getBoundingClientRect();
            return text && rect.width > 0 && rect.height > 0;
        });
        const savedSection = visible.filter((el) => {
            const text = (el.innerText || el.textContent || '').trim();
            const aria = (el.getAttribute('aria-label') || '').toLowerCase();
            const cls = (el.getAttribute('class') || '').toLowerCase();
            return aria.includes('filter') || cls.includes('filter') || text.toLowerCase().includes('filter');
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
        const candidates = Array.from(document.querySelectorAll('button, a, [role="button"], [data-state], [class*="filter"]'));
        const visible = candidates.filter((el) => {
            const text = (el.innerText || el.textContent || '').trim();
            const rect = el.getBoundingClientRect();
            if (!text || rect.width <= 0 || rect.height <= 0) return false;
            if (/^(show filters|save filter)$/i.test(text)) return false;
            const aria = (el.getAttribute('aria-label') || '').toLowerCase();
            const cls = (el.getAttribute('class') || '').toLowerCase();
            return aria.includes('filter') || cls.includes('filter') || text.toLowerCase().includes('filter');
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
```

- [ ] **Step 4: Run Hirify helper tests**

Run:

```bash
pytest tests/providers/hirify/test_scrape_jobs.py -v
```

Expected: all Hirify tests pass.

- [ ] **Step 5: Commit**

Run:

```bash
git add scripts/providers/hirify/scrape_jobs.py tests/providers/hirify/test_scrape_jobs.py
git commit -m "feat: collect hirify saved filter rows"
```

---

### Task 4: Add Pagination And Top-Level Hirify Scraper

**Files:**
- Modify: `scripts/providers/hirify/scrape_jobs.py`
- Test: `tests/providers/hirify/test_scrape_jobs.py`

- [ ] **Step 1: Add tests for pagination, dedup, and titles behavior**

Append these tests:

```python
def test_scrape_filter_pages_stops_when_next_disappears():
    from scripts.providers.hirify import scrape_jobs as mod

    page = MagicMock()
    with patch.object(mod, "_collect_current_page_jobs", side_effect=[
        [{"title": "AI Engineer", "company": "Acme", "url": "https://hirify.me/jobs/1"}],
        [{"title": "Backend Engineer", "company": "Beta", "url": "https://hirify.me/jobs/2"}],
    ]), patch.object(mod, "_click_next_page", side_effect=[True, False]):
        rows = mod._scrape_filter_pages(page)

    assert [r["url"] for r in rows] == ["https://hirify.me/jobs/1", "https://hirify.me/jobs/2"]


def test_scrape_jobs_dedups_across_filters_and_ignores_titles():
    from scripts.providers.hirify import scrape_jobs as mod

    pw_mock = MagicMock()
    page = MagicMock()
    ctx = MagicMock()
    ctx.new_page.return_value = page
    browser = MagicMock()
    browser.contexts = [ctx]
    pw_instance = MagicMock()
    pw_instance.chromium.connect_over_cdp.return_value = browser
    pw_mock.__enter__.return_value = pw_instance
    pw_mock.__exit__.return_value = False

    raw = [
        {"title": "Backend Engineer", "company": "Acme", "url": "https://hirify.me/jobs/1"},
        {"title": "Backend Engineer", "company": "Acme", "url": "https://hirify.me/jobs/1"},
    ]

    with patch.object(mod, "sync_playwright", return_value=pw_mock), \
         patch.object(mod, "_get_saved_filters", return_value=[{"index": 0, "label": "A"}, {"index": 1, "label": "B"}]), \
         patch.object(mod, "_activate_saved_filter"), \
         patch.object(mod, "_scrape_filter_pages", return_value=raw), \
         patch.object(mod, "is_relevant", return_value=True):
        jobs = mod.scrape_jobs("http://localhost:9222", titles=["AI Engineer"])

    assert len(jobs) == 1
    assert jobs[0].title == "Backend Engineer"
    page.goto.assert_called_once_with(mod.HIRIFY_BASE, wait_until="domcontentloaded", timeout=30000)
```

- [ ] **Step 2: Run the new tests and verify they fail**

Run:

```bash
pytest tests/providers/hirify/test_scrape_jobs.py::test_scrape_filter_pages_stops_when_next_disappears tests/providers/hirify/test_scrape_jobs.py::test_scrape_jobs_dedups_across_filters_and_ignores_titles -v
```

Expected: missing `_scrape_filter_pages`, `_click_next_page`, and `scrape_jobs`.

- [ ] **Step 3: Implement pagination helpers**

Append:

```python
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
```

- [ ] **Step 4: Implement `scrape_jobs`**

Append:

```python
def scrape_jobs(
    cdp_url: str,
    titles: list[str] | None = None,
    db_path: str | None = None,
    _config: dict | None = None,
) -> list[ShallowJob]:
    _ = titles, db_path, (_config if _config is not None else _load_config())
    raw_rows: list[dict] = []
    seen_urls: set[str] = set()

    with sync_playwright() as pw:
        browser = pw.chromium.connect_over_cdp(cdp_url)
        ctx = browser.contexts[0]
        page = ctx.new_page()
        try:
            page.goto(HIRIFY_BASE, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(2000)
            filters = _get_saved_filters(page)
            if not filters:
                print("[hirify] No saved filters found. Create saved filters on https://hirify.me/ first.", file=sys.stderr, flush=True)
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
                    print(f"[hirify] WARNING: saved filter {saved_filter.get('label', saved_filter.get('index'))!r} failed: {e}", file=sys.stderr, flush=True)
        finally:
            page.close()

    jobs: list[ShallowJob] = []
    for row in raw_rows:
        if not row.get("title") or not row.get("url"):
            continue
        jobs.append(_normalize_raw_job(row))
    return jobs
```

- [ ] **Step 5: Run Hirify tests**

Run:

```bash
pytest tests/providers/hirify/test_scrape_jobs.py -v
```

Expected: all Hirify tests pass.

- [ ] **Step 6: Commit**

Run:

```bash
git add scripts/providers/hirify/scrape_jobs.py tests/providers/hirify/test_scrape_jobs.py
git commit -m "feat: scrape hirify saved filters"
```

---

### Task 5: Add Hirify Auth Check

**Files:**
- Create: `scripts/providers/hirify/check_auth.py`
- Modify: `tests/providers/test_check_auth.py`
- Test: `tests/providers/hirify/test_scrape_jobs.py`

- [ ] **Step 1: Add unit tests for auth page detection**

Append to `tests/providers/hirify/test_scrape_jobs.py`:

```python
def test_hirify_auth_page_detection():
    from scripts.providers.hirify.check_auth import _is_auth_page

    assert _is_auth_page("https://hirify.me/?modal=login")
    assert _is_auth_page("https://accounts.google.com/o/oauth2/v2/auth")
    assert not _is_auth_page("https://hirify.me/")
```

- [ ] **Step 2: Run the auth unit test and verify it fails**

Run:

```bash
pytest tests/providers/hirify/test_scrape_jobs.py::test_hirify_auth_page_detection -v
```

Expected: import failure for missing `check_auth.py`.

- [ ] **Step 3: Implement Hirify auth check**

Create `scripts/providers/hirify/check_auth.py`:

```python
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from playwright.sync_api import sync_playwright

from scripts.providers._shared.auth_check import wait_for_auth

CHECK_URL = "https://hirify.me/"


class AuthError(Exception):
    pass


def _is_auth_page(url: str) -> bool:
    return bool(re.search(r"modal=login|sign.?in|accounts\.google\.com", url, re.I))


def _has_authenticated_controls(page) -> bool:
    try:
        text = (page.locator("body").inner_text(timeout=3000) or "").lower()
    except Exception:
        return False
    return "saved" in text and "sign in" not in text


def check_auth(cdp_url: str) -> None:
    with sync_playwright() as pw:
        browser = pw.chromium.connect_over_cdp(cdp_url)
        ctx = browser.contexts[0]
        page = ctx.new_page()
        try:
            ok = wait_for_auth(page, "hirify", CHECK_URL, _is_auth_page)
            if ok and not _has_authenticated_controls(page):
                ok = False
        finally:
            page.close()
    if not ok:
        raise AuthError("Hirify auth timed out")


if __name__ == "__main__":
    check_auth(sys.argv[1] if len(sys.argv) > 1 else "http://localhost:9222")
```

- [ ] **Step 4: Add optional live e2e auth test**

Append to `tests/providers/test_check_auth.py`:

```python
@pytest.mark.e2e
def test_hirify_check_auth():
    from scripts.providers.hirify.check_auth import check_auth
    check_auth(CDP_URL)
```

- [ ] **Step 5: Run auth tests**

Run:

```bash
pytest tests/providers/hirify/test_scrape_jobs.py::test_hirify_auth_page_detection -v
```

Expected: pass.

Do not run the live e2e test unless Chrome is running and Hirify login is available:

```bash
pytest tests/providers/test_check_auth.py::test_hirify_check_auth -m e2e -v -s
```

- [ ] **Step 6: Commit**

Run:

```bash
git add scripts/providers/hirify/check_auth.py tests/providers/test_check_auth.py tests/providers/hirify/test_scrape_jobs.py
git commit -m "feat: add hirify auth check"
```

---

### Task 6: Wire Hirify Into Config, Onboarding, Skills, Docs, And Dashboard

**Files:**
- Modify: `config/user.yaml.example`
- Modify: `skills/onboarding/SKILL.md`
- Modify: `skills/run-scraping-pipeline/SKILL.md`
- Modify: `README.md`
- Modify: `dashboard/app/components/JobList.tsx`
- Modify: `config/scraping-workflow.yaml`
- Test: `tests/providers/hirify/test_scrape_jobs.py`

- [ ] **Step 1: Add integration text/config tests**

Append:

```python
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def test_hirify_references_are_present_in_static_integration_files():
    expected = {
        "config/user.yaml.example": "hirify:",
        "skills/onboarding/SKILL.md": "Hirify",
        "skills/run-scraping-pipeline/SKILL.md": "hirify",
        "README.md": "Hirify",
        "dashboard/app/components/JobList.tsx": "hirify:",
    }

    for rel_path, needle in expected.items():
        assert needle in (ROOT / rel_path).read_text()
```

- [ ] **Step 2: Run the integration test and verify it fails**

Run:

```bash
pytest tests/providers/hirify/test_scrape_jobs.py::test_hirify_references_are_present_in_static_integration_files -v
```

Expected: fail for missing static references.

- [ ] **Step 3: Update config example**

In `config/user.yaml.example`, update providers:

```yaml
providers:
  greenhouse: true
  jobleads: true
  wellfound: true
  sprout: false
  hirify: false
```

- [ ] **Step 4: Update onboarding skill**

In `skills/onboarding/SKILL.md`:

- Change the welcome provider list to `Greenhouse, JobLeads, Wellfound, Sprout, Hirify`.
- Add provider option:

```markdown
> - **Hirify** (hirify.me) — saved-filter based IT and Digital aggregator
```

- Add generated config key:

```yaml
  hirify: false
```

- [ ] **Step 5: Update run-scraping skill**

In `skills/run-scraping-pipeline/SKILL.md`:

- Add `"run hirify" → hirify only` to triggers.
- Add `python3 scripts/scraping_pipeline.py --provider hirify` where provider pipeline commands are described.
- Add a provider note:

```markdown
### Hirify saved filters

Hirify does not use `search_terms`, `locations`, or `work_style` to build searches. The user must create saved filters on https://hirify.me/ first. The scraper opens every saved filter and collects all paginated jobs.
```

- [ ] **Step 6: Update README**

In `README.md`:

- Change the first workflow bullet to mention Hirify.
- Add supported board row:

```markdown
| [Hirify](https://hirify.me) | Saved-filter UI | IT and Digital aggregator; user-managed saved filters |
```

- Add a sentence under configuration:

```markdown
Hirify ignores `search_terms`, `locations`, and `work_style` for search construction; create saved filters on Hirify and enable `providers.hirify`.
```

- [ ] **Step 7: Update dashboard provider color**

In `dashboard/app/components/JobList.tsx`, update `PROVIDER_COLORS`:

```ts
export const PROVIDER_COLORS: Record<string, { bg: string; color: string }> = {
  greenhouse: { bg: "rgba(34,197,94,0.13)",   color: "#4ade80" },
  jobleads:   { bg: "rgba(251,146,60,0.13)",  color: "#fb923c" },
  wellfound:  { bg: "rgba(167,139,250,0.13)", color: "#a78bfa" },
  sprout:     { bg: "rgba(45,212,191,0.13)",  color: "#2dd4bf" },
  hirify:     { bg: "rgba(56,189,248,0.13)",  color: "#38bdf8" },
};
```

- [ ] **Step 8: Update workflow yaml**

In `config/scraping-workflow.yaml`, add this provider entry immediately after the Sprout entry if Sprout is present, otherwise immediately after the JobLeads entry:

```yaml
# ── Hirify ───────────────────────────────────────────────
- id: hirify
  enabled: false
  scraper:
    type: pipeline_provider
    script: scripts/scraping_pipeline.py
    command: >
      python3 scripts/scraping_pipeline.py
      --provider hirify
    timeout_seconds: 900
    artifact_pattern: "outputs/hirify/runs/hirify_jobs_live_YYYY-MM-DD.json"
  error_handling:
    on_failure: skip_provider
    notify_telegram: true
    retry: false
```

- [ ] **Step 9: Run integration test**

Run:

```bash
pytest tests/providers/hirify/test_scrape_jobs.py::test_hirify_references_are_present_in_static_integration_files -v
```

Expected: pass.

- [ ] **Step 10: Commit**

Run:

```bash
git add config/user.yaml.example skills/onboarding/SKILL.md skills/run-scraping-pipeline/SKILL.md README.md dashboard/app/components/JobList.tsx config/scraping-workflow.yaml tests/providers/hirify/test_scrape_jobs.py
git commit -m "docs: add hirify integration surfaces"
```

---

### Task 7: Final Verification And Manual Live Check

**Files:**
- No planned source edits unless verification finds a bug.

- [ ] **Step 1: Run focused unit tests**

Run:

```bash
pytest tests/providers/hirify/test_scrape_jobs.py tests/test_scraping_pipeline.py -v
```

Expected: pass.

- [ ] **Step 2: Run broader provider/pipeline tests**

Run:

```bash
pytest tests/providers tests/pipeline tests/test_scraping_pipeline.py -v
```

Expected: pass, excluding tests explicitly marked e2e unless the local test config includes them.

- [ ] **Step 3: Run dashboard static checks**

```bash
cd dashboard && npm run lint
```

```bash
cd dashboard && npm run build
```

Expected: no TypeScript or lint failures from the provider color change.

- [ ] **Step 4: Optional live Hirify smoke test**

Only run this with Chrome running at `localhost:9222`, the user logged into Hirify, and at least one saved filter configured:

```bash
python3 scripts/scraping_pipeline.py --provider hirify --cdp-url http://localhost:9222
```

Expected: output includes `[pipeline] hirify: scraped N jobs`. If `N` is `0`, inspect whether the Hirify account has saved filters and visible results.

- [ ] **Step 5: Commit fixes from verification**

If verification required changes, stage the exact files changed by the verification fixes and commit them. Example for a scraper fix:

```bash
git add scripts/providers/hirify/scrape_jobs.py tests/providers/hirify/test_scrape_jobs.py
git commit -m "fix: stabilize hirify provider"
```

If no fixes were needed, do not create an empty commit.

---

## Plan Self-Review

- Spec coverage: provider package, auth, saved filters, pagination, dedup, no title filtering, onboarding/docs/UI/config, and tests are covered by Tasks 1-7.
- Placeholder scan: no placeholder implementation steps remain.
- Type consistency: all provider functions use the current pipeline signature `scrape_jobs(cdp_url, titles=None, db_path=None, _config=None) -> list[ShallowJob]`; `JobDetail.tsx` reuses `PROVIDER_COLORS` from `JobList.tsx`.
