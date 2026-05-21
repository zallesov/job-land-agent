# JobLandAgent Sub-project A: Config Generalization Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove all personal data from the repo, introduce `config/user.yaml` as the single config source, migrate all four provider `scrape_jobs.py` to accept a location dict instead of a preset string key, and add `--titles` support to the scraping pipeline.

**Architecture:** Three change layers: (1) files/config — gitignore, user.yaml.example, requirements.txt, start-chrome.sh, hermes-profile sanitize; (2) Python interface — providers accept `location: dict` + `titles` param, pipeline resolves city string → dict from user.yaml; (3) tests — update existing + add provider interface tests.

**Tech Stack:** Python 3.11+, PyYAML, pytest, Playwright (mocked in tests)

---

## Chunk 1: Repo Hygiene & Static Files

### Task 1: Update .gitignore and archive deprecated skills

**Files:**
- Modify: `.gitignore`
- Move: `skills/daily-pipeline/` → `tmp/skills/daily-pipeline/`
- Move: `skills/job-scraping-pipeline/` → `tmp/skills/job-scraping-pipeline/`
- Move: `skills/greenhouse-scraper/` → `tmp/skills/greenhouse-scraper/`
- Move: `skills/jobleads-scraper/` → `tmp/skills/jobleads-scraper/`
- Move: `skills/greenhouse-daily-export/` → `tmp/skills/greenhouse-daily-export/`
- Move: `skills/jobleads-daily-export/` → `tmp/skills/jobleads-daily-export/`
- Move: `skills/assess-jobs-due-diligence/` → `tmp/skills/assess-jobs-due-diligence/`
- Move: `skills/consolidate-jobs-workbook/` → `tmp/skills/consolidate-jobs-workbook/`
- Move: `skills/scrape-and-research-job/` → `tmp/skills/scrape-and-research-job/`
- Delete: `config/pipeline_config.json`

- [ ] **Step 1: Append to .gitignore**

Open `.gitignore` and append at the end:

```
# User config (personal data — copy from user.yaml.example)
config/user.yaml
config/cv.md
config/resume.pdf

# Hermes profile personal data
hermes-profile/auth.json
hermes-profile/.env
hermes-profile/.hermes_history
hermes-profile/cache/
hermes-profile/audio_cache/
hermes-profile/cron/output/
hermes-profile/home/
hermes-profile/.skills_prompt_snapshot.json
hermes-profile/.update_check

# Legacy pipeline config (superseded by config/user.yaml)
config/pipeline_config.json

# Archived skills (kept for reference, not committed)
tmp/skills/

# Personal files
ALEKSANDR_*.md
jobs_all.*
```

- [ ] **Step 2: Create tmp/skills dir and move deprecated skills**

```bash
mkdir -p tmp/skills
git mv skills/daily-pipeline tmp/skills/daily-pipeline
git mv skills/job-scraping-pipeline tmp/skills/job-scraping-pipeline
git mv skills/greenhouse-scraper tmp/skills/greenhouse-scraper
git mv skills/jobleads-scraper tmp/skills/jobleads-scraper
git mv skills/greenhouse-daily-export tmp/skills/greenhouse-daily-export
git mv skills/jobleads-daily-export tmp/skills/jobleads-daily-export
git mv skills/assess-jobs-due-diligence tmp/skills/assess-jobs-due-diligence
git mv skills/consolidate-jobs-workbook tmp/skills/consolidate-jobs-workbook
git mv skills/scrape-and-research-job tmp/skills/scrape-and-research-job
```

- [ ] **Step 3: Delete pipeline_config.json**

```bash
git rm config/pipeline_config.json
```

- [ ] **Step 4: Stage already-deleted .codex/skills files**

The git status shows `.codex/skills/` SKILL.md files as already-deleted (`D` status). Stage them:

```bash
git add .codex/skills/ 2>/dev/null || true
```

- [ ] **Step 5: Verify skills dir only contains active skills**

```bash
ls skills/
# Expected: apply-job  enrich-job  job-research  sanity-check-job
```

- [ ] **Step 6: Commit**

```bash
git add .gitignore
git commit -m "chore: update gitignore, archive deprecated skills, remove pipeline_config"
```

---

### Task 2: Create config/user.yaml.example, requirements.txt, start-chrome.sh

**Files:**
- Create: `config/user.yaml.example`
- Create: `requirements.txt`
- Create: `start-chrome.sh` (copy from `~/start-chrome.sh`)

- [ ] **Step 1: Create config/user.yaml.example**

```bash
cat > config/user.yaml.example << 'EOF'
# User identity — used by apply-job skill
user:
  name: "Your Name"
  email: "you@example.com"
  linkedin_url: "https://linkedin.com/in/yourhandle"
  resume_pdf_path: "config/resume.pdf"

# CV in markdown format — used by enrich-job and sanity-check-job skills
cv_path: "config/cv.md"

# Target job locations — any city; country_code (ISO 3166-1 alpha-2) required for feed scrapers
locations:
  - city: "Berlin"
    country: "Germany"
    country_code: "DE"
  - city: "Barcelona"
    country: "Spain"
    country_code: "ES"

# Work style preference — used by sanity_check_job and job-research for scoring
work_style:
  preferred: "remote"          # remote | hybrid | onsite
  willing_to_relocate: false

# Job title search terms — used by Sprout and title filtering in other scrapers
search_terms:
  - "Software Engineer"
  - "AI Engineer"
  - "Engineering Manager"
  - "Platform Engineer"

# Active job board providers
providers:
  greenhouse: true
  jobleads: true
  wellfound: true
  sprout: false

# SQLite database path (relative to repo root)
db_path: "jobs.db"
EOF
```

- [ ] **Step 2: Create requirements.txt**

```bash
cat > requirements.txt << 'EOF'
playwright>=1.40.0
pyyaml>=6.0
pytest>=7.0
pytest-asyncio>=0.21
EOF
```

- [ ] **Step 3: Copy start-chrome.sh from home dir to repo root**

```bash
cp ~/start-chrome.sh ./start-chrome.sh
chmod +x start-chrome.sh
```

Verify it contains `--enable-automation`:
```bash
grep "enable-automation" start-chrome.sh
# Must print the flag
```

- [ ] **Step 4: Commit**

```bash
git add config/user.yaml.example requirements.txt start-chrome.sh
git commit -m "chore: add user.yaml.example, requirements.txt, start-chrome.sh"
```

---

### Task 3: Sanitize hermes-profile/config.yaml

**Files:**
- Modify: `hermes-profile/config.yaml`

**Context:** `hermes-profile/config.yaml` currently has a live DeepSeek API key at line 6 (`api_key: sk-fc57...`) and `skills.external_dirs` pointing to an absolute path. Both must change before committing.

> **WARNING:** The live API key at line 6 must be invalidated in the DeepSeek console before or after this step. The key `REDACTED_DEEPSEEK_API_KEY` will be committed as `""` — invalidate it separately.

- [ ] **Step 1: Blank the API key**

In `hermes-profile/config.yaml`, line 6, change:
```yaml
  api_key: REDACTED_DEEPSEEK_API_KEY
```
to:
```yaml
  api_key: ""
```

- [ ] **Step 2: Fix skills.external_dirs to relative path**

Find the `skills:` block (around line 368–371):
```yaml
skills:
  external_dirs:
  - /Users/zall/interviews/skills
```

Change to:
```yaml
skills:
  external_dirs:
  - ../skills
```

(Relative to `hermes-profile/`, `../skills` points to `skills/` at repo root.)

- [ ] **Step 3: Verify the file parses cleanly**

```bash
python3 -c "import yaml; yaml.safe_load(open('hermes-profile/config.yaml')); print('OK')"
# Expected: OK
```

- [ ] **Step 4: Commit**

```bash
git add hermes-profile/config.yaml
git commit -m "chore: remove live API key from hermes-profile config, fix skills path to relative"
```

---

## Chunk 2: Python Interface Changes

### Task 4: Add __main__ blocks to all four check_auth.py files

**Files:**
- Modify: `scripts/providers/greenhouse/check_auth.py`
- Modify: `scripts/providers/jobleads/check_auth.py`
- Modify: `scripts/providers/wellfound/check_auth.py`
- Modify: `scripts/providers/sprout/check_auth.py`

- [ ] **Step 1: Append __main__ block to greenhouse/check_auth.py**

Append to the end of `scripts/providers/greenhouse/check_auth.py`:

```python

if __name__ == "__main__":
    import sys
    check_auth(sys.argv[1] if len(sys.argv) > 1 else "http://localhost:9222")
```

- [ ] **Step 2: Append __main__ block to jobleads/check_auth.py**

Read `scripts/providers/jobleads/check_auth.py` first. Append at the end:

```python

if __name__ == "__main__":
    import sys
    check_auth(sys.argv[1] if len(sys.argv) > 1 else "http://localhost:9222")
```

- [ ] **Step 3: Append __main__ block to wellfound/check_auth.py**

Read `scripts/providers/wellfound/check_auth.py` first. Append at the end:

```python

if __name__ == "__main__":
    import sys
    check_auth(sys.argv[1] if len(sys.argv) > 1 else "http://localhost:9222")
```

- [ ] **Step 4: Append __main__ block to sprout/check_auth.py**

Read `scripts/providers/sprout/check_auth.py` first. Append at the end:

```python

if __name__ == "__main__":
    import sys
    check_auth(sys.argv[1] if len(sys.argv) > 1 else "http://localhost:9222")
```

- [ ] **Step 5: Verify importability (no syntax errors)**

```bash
python3 -c "
import sys; sys.path.insert(0, '.')
from scripts.providers.greenhouse.check_auth import check_auth
from scripts.providers.jobleads.check_auth import check_auth
from scripts.providers.wellfound.check_auth import check_auth
from scripts.providers.sprout.check_auth import check_auth
print('All check_auth modules import OK')
"
# Expected: All check_auth modules import OK
```

- [ ] **Step 6: Commit**

```bash
git add scripts/providers/greenhouse/check_auth.py \
        scripts/providers/jobleads/check_auth.py \
        scripts/providers/wellfound/check_auth.py \
        scripts/providers/sprout/check_auth.py
git commit -m "feat: add __main__ blocks to all provider check_auth scripts"
```

---

### Task 5: Migrate greenhouse and jobleads scrape_jobs.py to location dict

**Files:**
- Modify: `scripts/providers/greenhouse/scrape_jobs.py`
- Modify: `scripts/providers/jobleads/scrape_jobs.py`
- Test: `tests/test_scrape_jobs_location.py` (create)

**Context:** Feed-based scrapers (Greenhouse, JobLeads) build URLs from `country_code`. The `LOCATION_PRESETS` dicts in the legacy `scripts/scrape_greenhouse.py` / `scripts/scrape_jobleads.py` are no longer used by these providers.

> **NOTE — Country-level search:** The existing `LOCATION_PRESETS["berlin"]` used city-level lat/lon params for precise location filtering. The new dict-based interface uses country-level search (`country_short_name=<code>`) because `user.yaml` locations do not carry lat/lon. This is intentional per spec: `country_code` is the defined interface for feed-based scrapers. Results will be broader (all-Germany vs. Berlin-only) but Greenhouse's personalised "for you" feed already applies relevance ranking. Document this tradeoff to users in the README.

When `titles` is provided, filter results post-collection.

- [ ] **Step 1: Write failing tests for greenhouse location dict**

Create `tests/test_scrape_jobs_location.py`:

```python
"""Tests for provider scrape_jobs location dict interface."""
from unittest.mock import MagicMock, patch

BERLIN = {"city": "Berlin", "country": "Germany", "country_code": "DE"}
BARCELONA = {"city": "Barcelona", "country": "Spain", "country_code": "ES"}


def _make_playwright_mock(collect_return_value: list[dict]):
    """Return (pw_context_manager, mock_page) ready to use in patches."""
    mock_page = MagicMock()
    mock_ctx = MagicMock()
    mock_ctx.new_page.return_value = mock_page
    mock_browser = MagicMock()
    mock_browser.contexts = [mock_ctx]
    mock_pw_instance = MagicMock()
    mock_pw_instance.chromium.connect_over_cdp.return_value = mock_browser
    mock_pw_cm = MagicMock()
    mock_pw_cm.__enter__ = MagicMock(return_value=mock_pw_instance)
    mock_pw_cm.__exit__ = MagicMock(return_value=False)
    return mock_pw_cm


def test_greenhouse_accepts_location_dict_and_country_code():
    """greenhouse scrape_jobs uses country_code in URL, not LOCATION_PRESETS."""
    from scripts.providers.greenhouse import scrape_jobs as mod

    raw = [{"title": "AI Engineer", "company": "Acme", "url": "http://x.com",
            "location": "Remote", "country": "DE"}]
    pw_mock = _make_playwright_mock(raw)

    with patch.object(mod, "sync_playwright", return_value=pw_mock), \
         patch.object(mod, "collect_greenhouse", return_value=raw) as mock_collect, \
         patch.object(mod, "is_relevant", return_value=True):
        result = mod.scrape_jobs(BERLIN, "http://localhost:9222")

    # URL must use country_short_name=DE (country-level, not city-level lat/lon)
    search_arg = mock_collect.call_args[0][1]
    assert "country_short_name=DE" in search_arg["url"]
    assert "location_type=country" in search_arg["url"]
    assert len(result) == 1


def test_greenhouse_title_filter():
    """greenhouse scrape_jobs filters by titles when provided."""
    from scripts.providers.greenhouse import scrape_jobs as mod

    raw = [
        {"title": "Software Engineer", "company": "Acme", "url": "http://a.com",
         "location": "Remote", "country": "DE"},
        {"title": "AI Engineer", "company": "Acme", "url": "http://b.com",
         "location": "Remote", "country": "DE"},
    ]
    pw_mock = _make_playwright_mock(raw)

    with patch.object(mod, "sync_playwright", return_value=pw_mock), \
         patch.object(mod, "collect_greenhouse", return_value=raw), \
         patch.object(mod, "is_relevant", return_value=True):
        result = mod.scrape_jobs(BERLIN, "http://localhost:9222", titles=["AI Engineer"])

    assert len(result) == 1
    assert result[0].title == "AI Engineer"


def test_jobleads_accepts_location_dict():
    """jobleads scrape_jobs uses country_code in URL."""
    from scripts.providers.jobleads import scrape_jobs as mod

    raw = [{"title": "Platform Engineer", "company": "Corp", "url": "http://c.com",
            "location": "Remote", "country": "ES"}]
    pw_mock = _make_playwright_mock(raw)

    with patch.object(mod, "sync_playwright", return_value=pw_mock), \
         patch.object(mod, "collect_jobleads", return_value=raw) as mock_collect, \
         patch.object(mod, "is_relevant", return_value=True):
        result = mod.scrape_jobs(BARCELONA, "http://localhost:9222")

    search_arg = mock_collect.call_args[0][1]
    assert "location_country=ES" in search_arg["url"]
    assert len(result) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python3 -m pytest tests/test_scrape_jobs_location.py -v 2>&1 | head -40
# Expected: FAIL (scrape_jobs still takes string, not dict)
```

- [ ] **Step 3: Rewrite greenhouse/scrape_jobs.py**

Replace entire `scripts/providers/greenhouse/scrape_jobs.py`:

```python
from __future__ import annotations
from urllib.parse import quote_plus
from playwright.sync_api import sync_playwright

from scripts.pipeline.types import ShallowJob
from scripts.providers._shared.job_filter import is_relevant
from scripts.scrape_greenhouse import GREENHOUSE_BASE, collect_greenhouse


def scrape_jobs(
    location: dict,
    cdp_url: str,
    titles: list[str] | None = None,
) -> list[ShallowJob]:
    country_code = location["country_code"]
    country = location["country"]
    city = location["city"]
    url_params = (
        f"location={quote_plus(country)}&location_type=country"
        f"&country_short_name={country_code}"
    )
    search = {
        "label": f"{city} Remote",
        "query": "",
        "country": country,
        "locationLabel": f"{city} Remote",
        "url": f"{GREENHOUSE_BASE}?view=for-you&{url_params}&work_type[]=remote",
    }

    raw_rows: list[dict] = []
    with sync_playwright() as pw:
        browser = pw.chromium.connect_over_cdp(cdp_url)
        ctx = browser.contexts[0]
        page = ctx.new_page()
        try:
            raw_rows = collect_greenhouse(page, search)
        finally:
            page.close()

    jobs: list[ShallowJob] = []
    for r in raw_rows:
        if not r.get("title") or not r.get("company"):
            continue
        j = ShallowJob(
            provider="greenhouse",
            title=r["title"],
            company=r["company"],
            url=r["url"],
            location=r.get("location", ""),
            country=r.get("country"),
            dedup_key=f"{r['company']}::{r['title']}",
            posting_date=r.get("postingDate") or None,
            salary_raw=r.get("salaryRaw") or None,
        )
        if is_relevant({"title": j.title}):
            jobs.append(j)

    if titles:
        jobs = [j for j in jobs if any(t.lower() in j.title.lower() for t in titles)]
    return jobs
```

- [ ] **Step 4: Rewrite jobleads/scrape_jobs.py**

Replace entire `scripts/providers/jobleads/scrape_jobs.py`:

```python
from __future__ import annotations
from playwright.sync_api import sync_playwright

from scripts.pipeline.types import ShallowJob
from scripts.providers._shared.job_filter import is_relevant
from scripts.scrape_jobleads import JOBLEADS_BASE, collect_jobleads


def scrape_jobs(
    location: dict,
    cdp_url: str,
    titles: list[str] | None = None,
) -> list[ShallowJob]:
    country_code = location["country_code"]
    country = location["country"]
    city = location["city"]
    url_params = (
        f"location_country={country_code}"
        f"&filter_by_contractType=full_time"
        f"&filter_by_remote=remote"
        f"&minSalary=100000"
    )
    search = {
        "label": f"{city} Remote",
        "query": "",
        "country": country,
        "url": f"{JOBLEADS_BASE}?view=for-you&{url_params}",
    }

    raw_rows: list[dict] = []
    with sync_playwright() as pw:
        browser = pw.chromium.connect_over_cdp(cdp_url)
        ctx = browser.contexts[0]
        page = ctx.new_page()
        try:
            raw_rows = collect_jobleads(page, search)
        finally:
            page.close()

    jobs: list[ShallowJob] = []
    for r in raw_rows:
        if not r.get("title") or not r.get("company"):
            continue
        j = ShallowJob(
            provider="jobleads",
            title=r["title"],
            company=r["company"],
            url=r["url"],
            location=r.get("location", ""),
            country=r.get("country"),
            dedup_key=f"{r['company']}::{r['title']}",
            posting_date=None,
            salary_raw=r.get("salaryRaw") or None,
        )
        if is_relevant({"title": j.title}):
            jobs.append(j)

    if titles:
        jobs = [j for j in jobs if any(t.lower() in j.title.lower() for t in titles)]
    return jobs
```

- [ ] **Step 5: Run tests**

```bash
python3 -m pytest tests/test_scrape_jobs_location.py::test_greenhouse_accepts_location_dict_and_country_code \
                  tests/test_scrape_jobs_location.py::test_greenhouse_title_filter \
                  tests/test_scrape_jobs_location.py::test_jobleads_accepts_location_dict -v
# Expected: 3 PASSED
```

- [ ] **Step 6: Commit**

```bash
git add scripts/providers/greenhouse/scrape_jobs.py \
        scripts/providers/jobleads/scrape_jobs.py \
        tests/test_scrape_jobs_location.py
git commit -m "feat: greenhouse and jobleads scrape_jobs accept location dict + titles filter"
```

---

### Task 6: Migrate wellfound and sprout scrape_jobs.py to location dict

**Files:**
- Modify: `scripts/providers/wellfound/scrape_jobs.py`
- Modify: `scripts/providers/sprout/scrape_jobs.py`
- Modify: `tests/test_scrape_jobs_location.py` (add tests)

**Context:**
- Wellfound is UI-based: uses `f"{city}, {country}"` as the location search string (same as existing `LOCATION_PRESETS["berlin"] = "Berlin, Germany"`).
- Sprout is UI-based: uses `city` string and passes `titles` directly to `collect_sprout`. No post-collection filtering needed for sprout — titles are search terms, not filters.

- [ ] **Step 1: Add wellfound and sprout tests to test_scrape_jobs_location.py**

Append to `tests/test_scrape_jobs_location.py`:

```python

def test_wellfound_uses_city_country_query():
    """wellfound scrape_jobs passes 'City, Country' to change_location."""
    from scripts.providers.wellfound import scrape_jobs as mod

    pw_mock = _make_playwright_mock([])

    with patch.object(mod, "sync_playwright", return_value=pw_mock), \
         patch.object(mod, "apply_filters"), \
         patch.object(mod, "change_location") as mock_change_location, \
         patch.object(mod, "scroll_to_load_all"), \
         patch.object(mod, "collect_wellfound", return_value=[]):
        mod.scrape_jobs(BERLIN, "http://localhost:9222")

    mock_change_location.assert_called_once()
    location_arg = mock_change_location.call_args[0][1]
    assert "Berlin" in location_arg
    assert "Germany" in location_arg


def test_sprout_passes_titles_to_collect():
    """sprout scrape_jobs passes titles to collect_sprout."""
    from scripts.providers.sprout import scrape_jobs as mod

    pw_mock = _make_playwright_mock([])

    with patch.object(mod, "sync_playwright", return_value=pw_mock), \
         patch.object(mod, "collect_sprout", return_value=[]) as mock_collect:
        mod.scrape_jobs(BERLIN, "http://localhost:9222", titles=["AI Engineer"])

    collect_kwargs = mock_collect.call_args[1]
    assert collect_kwargs["titles"] == ["AI Engineer"]
    assert collect_kwargs["location"] == "Berlin"


def test_sprout_uses_default_titles_when_none():
    """sprout falls back to DEFAULT_TITLES when titles=None."""
    from scripts.providers.sprout import scrape_jobs as mod
    from scripts.providers.sprout.scrape_jobs import DEFAULT_TITLES

    pw_mock = _make_playwright_mock([])

    with patch.object(mod, "sync_playwright", return_value=pw_mock), \
         patch.object(mod, "collect_sprout", return_value=[]) as mock_collect:
        mod.scrape_jobs(BERLIN, "http://localhost:9222")

    collect_kwargs = mock_collect.call_args[1]
    assert collect_kwargs["titles"] == DEFAULT_TITLES
```

- [ ] **Step 2: Run new tests to verify they fail**

```bash
python3 -m pytest tests/test_scrape_jobs_location.py::test_wellfound_uses_city_country_query \
                  tests/test_scrape_jobs_location.py::test_sprout_passes_titles_to_collect \
                  tests/test_scrape_jobs_location.py::test_sprout_uses_default_titles_when_none -v
# Expected: FAIL
```

- [ ] **Step 3: Rewrite wellfound/scrape_jobs.py**

Replace entire `scripts/providers/wellfound/scrape_jobs.py`:

```python
from __future__ import annotations
from playwright.sync_api import sync_playwright

from scripts.pipeline.types import ShallowJob
from scripts.providers._shared.job_filter import is_relevant
from scripts.scrape_wellfound import (
    WELLFOUND_BASE,
    apply_filters, change_location, scroll_to_load_all, collect_wellfound,
)


def scrape_jobs(
    location: dict,
    cdp_url: str,
    titles: list[str] | None = None,
) -> list[ShallowJob]:
    city = location["city"]
    country = location["country"]
    location_query = f"{city}, {country}"

    raw_rows: list[dict] = []
    with sync_playwright() as pw:
        browser = pw.chromium.connect_over_cdp(cdp_url)
        ctx = browser.contexts[0]
        page = ctx.new_page()
        try:
            page.goto(f"{WELLFOUND_BASE}/jobs", wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(2000)
            apply_filters(page)
            change_location(page, location_query)
            scroll_to_load_all(page)
            raw_rows = collect_wellfound(page, country)
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
        )
        if is_relevant({"title": j.title}):
            jobs.append(j)

    if titles:
        jobs = [j for j in jobs if any(t.lower() in j.title.lower() for t in titles)]
    return jobs
```

- [ ] **Step 4: Rewrite sprout/scrape_jobs.py**

Replace entire `scripts/providers/sprout/scrape_jobs.py`:

```python
from __future__ import annotations
from playwright.sync_api import sync_playwright

from scripts.pipeline.types import ShallowJob
from scripts.providers._shared.job_filter import is_relevant
from scripts.scrape_sprout import SPROUT_BASE, collect_sprout

DEFAULT_TITLES = [
    "Software Engineer", "Backend Engineer", "AI Engineer",
    "Platform Engineer", "Engineering Manager",
]


def scrape_jobs(
    location: dict,
    cdp_url: str,
    titles: list[str] | None = None,
) -> list[ShallowJob]:
    city = location["city"]
    country = location["country"]
    effective_titles = titles or DEFAULT_TITLES

    raw_rows: list[dict] = []
    with sync_playwright() as pw:
        browser = pw.chromium.connect_over_cdp(cdp_url)
        ctx = browser.contexts[0]
        page = ctx.new_page()
        try:
            page.goto(f"{SPROUT_BASE}/jobs", wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(2000)
            raw_rows = collect_sprout(
                page,
                titles=effective_titles,
                location=city,
                country=country,
            )
        finally:
            page.close()

    jobs: list[ShallowJob] = []
    for r in raw_rows:
        if not r.get("title") or not r.get("company"):
            continue
        j = ShallowJob(
            provider="sprout",
            title=r["title"],
            company=r["company"],
            url=r["url"],
            location=r.get("location", ""),
            country=r.get("country") or country,
            dedup_key=f"{r['company']}::{r['title']}",
            posting_date=None,
            salary_raw=r.get("salary") or None,
        )
        if is_relevant({"title": j.title}):
            jobs.append(j)
    return jobs
```

- [ ] **Step 5: Run all location tests**

```bash
python3 -m pytest tests/test_scrape_jobs_location.py -v
# Expected: 6 PASSED
```

- [ ] **Step 6: Commit**

```bash
git add scripts/providers/wellfound/scrape_jobs.py \
        scripts/providers/sprout/scrape_jobs.py \
        tests/test_scrape_jobs_location.py
git commit -m "feat: wellfound and sprout scrape_jobs accept location dict + titles param"
```

---

### Task 7: Update scraping_pipeline.py — location dict + --titles arg

**Files:**
- Modify: `scripts/scraping_pipeline.py`
- Modify: `tests/test_scraping_pipeline.py`

**Context:**
- `run()` now takes `location: dict` (not `str`) and `titles: list[str] | None = None`.
- `main()` reads `config/user.yaml`, resolves `--location <city>` to the dict, and parses `--titles` comma-separated string.
- The existing `test_scraping_pipeline.py` passes `location="berlin"` (string) — must update to pass a dict.

- [ ] **Step 1: Update test_scraping_pipeline.py**

Open `tests/test_scraping_pipeline.py`. Add this constant at the top of the file, after the imports:

```python
BERLIN = {"city": "Berlin", "country": "Germany", "country_code": "DE"}
```

**In `test_happy_path`:** change `location="berlin"` → `location=BERLIN` and update assertion:
```python
# Before:
run(provider="greenhouse", location="berlin", cdp_url="http://localhost:9222", db_path=db_path, ...)
mock_scrape.assert_called_once_with("berlin", "http://localhost:9222")

# After:
run(provider="greenhouse", location=BERLIN, cdp_url="http://localhost:9222", db_path=db_path, ...)
mock_scrape.assert_called_once_with(BERLIN, "http://localhost:9222", titles=None)
```

**In `test_auth_error_stops_pipeline`:** change `location="berlin"` → `location=BERLIN` (no assertion change needed):
```python
# Before:
run(provider="greenhouse", location="berlin", cdp_url="http://localhost:9222", db_path=db_path, ...)

# After:
run(provider="greenhouse", location=BERLIN, cdp_url="http://localhost:9222", db_path=db_path, ...)
```

**In `test_enrich_failure_skips_sanity_for_that_job`:** same change `location="berlin"` → `location=BERLIN`:
```python
# Before:
run(provider="greenhouse", location="berlin", cdp_url="http://localhost:9222", db_path=db_path, ...)

# After:
run(provider="greenhouse", location=BERLIN, cdp_url="http://localhost:9222", db_path=db_path, ...)
```

- [ ] **Step 2: Run existing tests to confirm they fail**

```bash
python3 -m pytest tests/test_scraping_pipeline.py -v
# Expected: FAIL (run() still takes str location)
```

- [ ] **Step 3: Rewrite scraping_pipeline.py**

Replace entire `scripts/scraping_pipeline.py`:

```python
#!/usr/bin/env python3
"""
Scraping pipeline orchestrator.

Usage:
  python3 scripts/scraping_pipeline.py --provider greenhouse --location Berlin
  python3 scripts/scraping_pipeline.py --provider jobleads --location Spain \
    --titles "Software Engineer,AI Engineer"

Options:
  --provider <name>   Provider: greenhouse | jobleads | wellfound | sprout
  --location <city>   City name — must match a location entry in config/user.yaml
  --titles <str>      Comma-separated job title search terms (optional)
  --cdp-url <url>     CDP endpoint (default: http://localhost:9222)
  --db <path>         DB path (default: jobs.db in project root)
"""
from __future__ import annotations

import argparse
import importlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.pipeline.dedup import dedup_jobs
from scripts.pipeline.ingest import ingest_jobs
from scripts.pipeline.enrich_job import enrich_job
from scripts.pipeline.sanity_check_job import sanity_check_job
from scripts.pipeline.notify import send_daily_digest

PROJECT_ROOT = Path(__file__).parent.parent
DEFAULT_DB = str(PROJECT_ROOT / "jobs.db")
DEFAULT_CDP = "http://localhost:9222"
PROVIDERS = {"greenhouse", "jobleads", "wellfound", "sprout"}


def run(
    provider: str,
    location: dict,
    titles: list[str] | None = None,
    cdp_url: str = DEFAULT_CDP,
    db_path: str = DEFAULT_DB,
    _check_auth=None,
    _scrape_jobs=None,
) -> None:
    if _check_auth is None:
        _check_auth = importlib.import_module(f"scripts.providers.{provider}.check_auth").check_auth
    if _scrape_jobs is None:
        _scrape_jobs = importlib.import_module(f"scripts.providers.{provider}.scrape_jobs").scrape_jobs
    check_auth_fn = _check_auth
    scrape_jobs_fn = _scrape_jobs

    check_auth_fn(cdp_url)

    try:
        raw_jobs = scrape_jobs_fn(location, cdp_url, titles=titles)
    except Exception as e:
        from scripts.telegram_notify import pipeline_failure
        pipeline_failure(provider, "scrape", str(e), "")
        raise

    print(f"[pipeline] {provider}: scraped {len(raw_jobs)} jobs", flush=True)

    new_jobs = dedup_jobs(raw_jobs, db_path=db_path)
    print(f"[pipeline] {len(new_jobs)} new after dedup", flush=True)

    job_ids = ingest_jobs(new_jobs, db_path=db_path)
    print(f"[pipeline] ingested {len(job_ids)} jobs", flush=True)

    enrich_failures: list[tuple[int, str]] = []
    enriched_ids: list[int] = []
    for job_id in job_ids:
        result = enrich_job(job_id, db_path=db_path)
        if result.success:
            enriched_ids.append(job_id)
        else:
            enrich_failures.append((job_id, result.error or "unknown"))

    sanity_failures: list[tuple[int, str]] = []
    for job_id in enriched_ids:
        result = sanity_check_job(job_id, db_path=db_path)
        if not result.success:
            sanity_failures.append((job_id, result.error or "unknown"))

    send_daily_digest(enrich_failures=enrich_failures, sanity_failures=sanity_failures)
    print(
        f"[pipeline] done. enrich_failures={len(enrich_failures)} "
        f"sanity_failures={len(sanity_failures)}",
        flush=True,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", required=True, choices=PROVIDERS)
    parser.add_argument("--location", required=True,
                        help="City name matching a location entry in config/user.yaml")
    parser.add_argument("--titles", default=None,
                        help="Comma-separated job title search terms")
    parser.add_argument("--cdp-url", default=DEFAULT_CDP)
    parser.add_argument("--db", default=DEFAULT_DB)
    args = parser.parse_args()

    import yaml
    config_path = PROJECT_ROOT / "config" / "user.yaml"
    if not config_path.exists():
        print(f"ERROR: {config_path} not found. Copy config/user.yaml.example to config/user.yaml and fill it in.",
              file=sys.stderr)
        return 1
    config = yaml.safe_load(config_path.read_text())
    location_dict = next(
        (loc for loc in config.get("locations", [])
         if loc["city"].lower() == args.location.lower()),
        None,
    )
    if location_dict is None:
        available = [loc["city"] for loc in config.get("locations", [])]
        print(f"ERROR: Location {args.location!r} not found in config/user.yaml. "
              f"Available: {available}", file=sys.stderr)
        return 1

    titles = [t.strip() for t in args.titles.split(",")] if args.titles else None

    run(
        provider=args.provider,
        location=location_dict,
        titles=titles,
        cdp_url=args.cdp_url,
        db_path=args.db,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Also add a test for titles being passed through**

Add to `tests/test_scraping_pipeline.py` a new test after the existing ones:

```python
def test_titles_passed_to_scrape_jobs(db_path):
    mock_check_auth = MagicMock()
    mock_scrape = MagicMock(return_value=[])

    with patch("scripts.scraping_pipeline.dedup_jobs", return_value=[]), \
         patch("scripts.scraping_pipeline.ingest_jobs", return_value=[]), \
         patch("scripts.scraping_pipeline.send_daily_digest"):
        from scripts.scraping_pipeline import run
        run(
            provider="greenhouse", location=BERLIN,
            titles=["AI Engineer", "Software Engineer"],
            cdp_url="http://localhost:9222", db_path=db_path,
            _check_auth=mock_check_auth, _scrape_jobs=mock_scrape,
        )

    mock_scrape.assert_called_once_with(
        BERLIN, "http://localhost:9222", titles=["AI Engineer", "Software Engineer"]
    )
```

- [ ] **Step 5: Run all scraping_pipeline tests**

```bash
python3 -m pytest tests/test_scraping_pipeline.py -v
# Expected: 4 PASSED (3 existing updated + 1 new)
```

- [ ] **Step 6: Run full test suite to check no regressions**

```bash
python3 -m pytest tests/ -v --ignore=tests/e2e
# Expected: all non-e2e tests pass
```

- [ ] **Step 7: Commit**

```bash
git add scripts/scraping_pipeline.py tests/test_scraping_pipeline.py
git commit -m "feat: scraping_pipeline accepts location dict + --titles arg; resolves city from user.yaml"
```

---

## Chunk 3: Verification

### Task 8: Final smoke test and cleanup

**Files:** None (verification only)

- [ ] **Step 1: Verify full test suite passes**

```bash
python3 -m pytest tests/ -v --ignore=tests/e2e
# Expected: all pass
```

- [ ] **Step 2: Verify pipeline CLI help works**

```bash
python3 -m pytest tests/ -k "not e2e" --tb=short
# Then verify CLI doesn't crash:
python3 scripts/scraping_pipeline.py --help
# Expected: prints usage without error
```

- [ ] **Step 3: Verify check_auth scripts run as __main__ (expect AuthError since no Chrome)**

```bash
python3 scripts/providers/greenhouse/check_auth.py 2>&1 | grep -E "AuthError|auth|Error" | head -3
# Expected: some error about connection/auth (not "ModuleNotFoundError" or "SyntaxError")
```

- [ ] **Step 4: Verify hermes-profile/config.yaml has no live API key**

```bash
grep "api_key" hermes-profile/config.yaml | head -5
# Expected: api_key: "" (blank) for the main model key
```

- [ ] **Step 5: Verify config/user.yaml.example parses**

```bash
python3 -c "import yaml; d = yaml.safe_load(open('config/user.yaml.example')); print('locations:', [l['city'] for l in d['locations']]); print('work_style:', d['work_style'])"
# Expected: locations: ['Berlin', 'Barcelona']  work_style: {'preferred': 'remote', 'willing_to_relocate': False}
```

- [ ] **Step 6: Final commit if any loose files**

```bash
git status
# If anything unstaged: git add -A && git commit -m "chore: sub-project A cleanup"
```
