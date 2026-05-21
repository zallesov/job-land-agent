# Scraping Pipeline Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restructure the scraping pipeline into a modular, testable architecture with per-provider check_auth/scrape_jobs modules and shared pipeline steps (dedup, ingest, enrich, sanity_check, notify).

**Architecture:** `scraping_pipeline.py` orchestrates Python functions imported from `scripts/pipeline/` (dedup, ingest, enrich_job, sanity_check_job, notify) and `scripts/providers/{provider}/` (check_auth, scrape_jobs). Hermes AI calls are isolated in `pipeline/hermes.py` using the `AIAgent` Python library. All DB writes happen in Python, not inside Hermes.

**Tech Stack:** Python 3.11+, Playwright (via CDP), SQLite (scripts/db.py), Hermes Python library (`run_agent.AIAgent`), pytest, unittest.mock

**Spec:** `docs/superpowers/specs/2026-05-21-scraping-pipeline-design.md`

---

## Chunk 1: Foundation

### Task 1: DB migration + `get_job()` + `update_job_status()` + dashboard STATUS

**Files:**
- Modify: `scripts/db.py`
- Modify: `dashboard/app/components/JobList.tsx`

- [ ] **Step 1: Write failing tests for new db.py functions**

```python
# scripts/test_db.py  (append to existing)
import sqlite3, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from scripts.db import create_db, get_job, update_job_status, get_connection

def _make_db(tmp_path):
    p = str(tmp_path / "t.db")
    create_db(p)
    return p

def test_get_job_returns_dict(tmp_path):
    p = _make_db(tmp_path)
    con = get_connection(p)
    jid = con.execute(
        "INSERT INTO jobs (url, provider, status) VALUES ('http://x.com','test','new')"
    ).lastrowid
    con.commit()
    job = get_job(con, jid)
    assert job["id"] == jid
    assert job["status"] == "new"
    con.close()

def test_get_job_missing_returns_none(tmp_path):
    p = _make_db(tmp_path)
    con = get_connection(p)
    assert get_job(con, 99999) is None
    con.close()

def test_update_job_status(tmp_path):
    p = _make_db(tmp_path)
    con = get_connection(p)
    jid = con.execute(
        "INSERT INTO jobs (url, provider, status) VALUES ('http://x.com','test','listed')"
    ).lastrowid
    con.commit()
    update_job_status(con, jid, "enrich_failed", comment="timeout")
    con.commit()
    job = get_job(con, jid)
    assert job["status"] == "enrich_failed"
    assert job["comment"] == "timeout"
    con.close()

def test_dedup_key_column_exists(tmp_path):
    p = _make_db(tmp_path)
    con = get_connection(p)
    con.execute("INSERT INTO jobs (url, provider, dedup_key) VALUES ('http://y.com','test','Co::Title')")
    con.commit()
    row = con.execute("SELECT dedup_key FROM jobs WHERE url='http://y.com'").fetchone()
    assert row["dedup_key"] == "Co::Title"
    con.close()

def test_dedup_key_unique(tmp_path):
    import pytest
    p = _make_db(tmp_path)
    con = get_connection(p)
    con.execute("INSERT INTO jobs (url, provider, dedup_key) VALUES ('http://a.com','t','Co::T')")
    con.commit()
    with pytest.raises(Exception):
        con.execute("INSERT INTO jobs (url, provider, dedup_key) VALUES ('http://b.com','t','Co::T')")
        con.commit()
    con.close()
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd /Users/zall/interviews
python -m pytest scripts/test_db.py::test_get_job_returns_dict scripts/test_db.py::test_dedup_key_column_exists -v
```
Expected: FAIL — `get_job`, `update_job_status` not defined; `dedup_key` column missing.

- [ ] **Step 3: Add `get_job`, `update_job_status` and DB migration to `scripts/db.py`**

Add after the existing `get_job_by_url` function:

```python
def get_job(con: sqlite3.Connection, job_id: int) -> dict | None:
    row = con.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    return dict(row) if row else None


def update_job_status(con: sqlite3.Connection, job_id: int, status: str,
                      comment: str | None = None) -> None:
    if comment is not None:
        con.execute(
            "UPDATE jobs SET status = ?, comment = ?, updated_at = datetime('now') WHERE id = ?",
            (status, comment, job_id),
        )
    else:
        con.execute(
            "UPDATE jobs SET status = ?, updated_at = datetime('now') WHERE id = ?",
            (status, job_id),
        )
```

Add to the migration block inside `create_db()` (after the existing migrations):

```python
        "ALTER TABLE jobs ADD COLUMN dedup_key TEXT",
```

And after the migration loop, add the unique index (safe to run multiple times):

```python
    try:
        cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_jobs_dedup_key ON jobs(dedup_key)")
        con.commit()
    except Exception:
        pass
```

- [ ] **Step 4: Run tests — all pass**

```bash
python -m pytest scripts/test_db.py -v
```
Expected: all existing tests + 5 new tests PASS.

- [ ] **Step 5: Update `dashboard/app/components/JobList.tsx`**

In `STATUS_COLORS`, add after `archived`:

```typescript
  listed:        "bg-slate-900/60 text-slate-400",
  enrich_failed: "bg-red-900/20 text-red-600",
  sanity_failed: "bg-orange-900/20 text-orange-600",
```

In `STATUS_PRIORITY`, add after `archived: 9`:

```typescript
  listed: 5.5, enrich_failed: 10, sanity_failed: 11,
```

- [ ] **Step 6: Commit**

```bash
git add scripts/db.py dashboard/app/components/JobList.tsx scripts/test_db.py
git commit -m "feat: add dedup_key column, get_job/update_job_status helpers, new pipeline statuses"
```

---

### Task 2: Type definitions + `__init__.py` files + shared utilities

**Files:**
- Create: `scripts/__init__.py` (if missing)
- Create: `scripts/pipeline/__init__.py`
- Create: `scripts/pipeline/types.py`
- Create: `scripts/providers/__init__.py`
- Create: `scripts/providers/_shared/__init__.py`
- Create: `scripts/providers/_shared/auth_check.py`
- Create: `scripts/providers/_shared/job_filter.py`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`
- Create: `tests/pipeline/__init__.py`

- [ ] **Step 1: Create package `__init__.py` files**

```bash
touch /Users/zall/interviews/scripts/__init__.py
touch /Users/zall/interviews/scripts/pipeline/__init__.py
touch /Users/zall/interviews/scripts/providers/__init__.py
touch /Users/zall/interviews/scripts/providers/_shared/__init__.py
touch /Users/zall/interviews/tests/__init__.py
touch /Users/zall/interviews/tests/pipeline/__init__.py
mkdir -p /Users/zall/interviews/tests/providers /Users/zall/interviews/tests/fixtures/hermes /Users/zall/interviews/tests/fixtures/greenhouse /Users/zall/interviews/tests/e2e
touch /Users/zall/interviews/tests/providers/__init__.py
touch /Users/zall/interviews/tests/e2e/__init__.py
```

- [ ] **Step 2: Create `scripts/pipeline/types.py`**

```python
from __future__ import annotations
from dataclasses import dataclass


@dataclass
class ShallowJob:
    provider: str
    title: str
    company: str
    url: str
    location: str
    country: str | None
    dedup_key: str        # "{company}::{title}"
    posting_date: str | None
    salary_raw: str | None


@dataclass
class HermesResult:
    success: bool
    data: dict
    error: str | None
    raw_output: str
```

- [ ] **Step 3: Create `scripts/providers/_shared/auth_check.py`**

Copy and adapt from existing `scripts/auth_check.py` — same logic, updated docstring:

```python
from __future__ import annotations
import subprocess
import sys
import time
from typing import Callable

HERMES = "/Users/zall/.local/bin/hermes"
TELEGRAM_TARGET = "telegram"


def _notify(msg: str) -> None:
    subprocess.run(
        [HERMES, "send", "--to", TELEGRAM_TARGET, msg],
        capture_output=True,
    )


def wait_for_auth(
    page,
    provider: str,
    check_url: str,
    is_auth_page_fn: Callable[[str], bool],
    timeout_sec: int = 600,
    poll_sec: int = 15,
) -> bool:
    """Navigate to check_url; if auth required, notify via Telegram and poll.

    Returns True on success, False on timeout (caller raises AuthError).
    """
    try:
        page.goto(check_url, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(2000)
    except Exception as e:
        print(f"[auth_check] Navigation error for {provider}: {e}", file=sys.stderr, flush=True)
        return False

    if not is_auth_page_fn(page.url):
        print(f"[auth_check] {provider}: authenticated ✓", flush=True)
        return True

    _notify(
        f"⚠️ Auth required: {provider}\n"
        f"Log in in the Chrome window.\n"
        f"Timeout: {timeout_sec // 60} min."
    )
    print(f"\n⚠️  AUTH REQUIRED: {provider}. Waiting up to {timeout_sec}s...", flush=True)

    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        time.sleep(poll_sec)
        current_url = page.url if page else ""
        if not is_auth_page_fn(current_url):
            print(f"✅ {provider}: login detected.", flush=True)
            _notify(f"✅ {provider} authenticated — pipeline resuming.")
            return True
        remaining = int(deadline - time.time())
        print(f"  [{provider}] still waiting... {remaining}s left", flush=True)

    print(f"❌ {provider}: auth timed out.", file=sys.stderr, flush=True)
    _notify(f"❌ {provider} auth timed out ({timeout_sec // 60} min). Provider skipped.")
    return False
```

- [ ] **Step 4: Create `scripts/providers/_shared/job_filter.py`**

This is a re-export of the existing filter so providers import from one consistent path:

```python
from scripts.job_filter import is_relevant  # noqa: F401
```

- [ ] **Step 5: Create `tests/conftest.py`**

```python
from __future__ import annotations
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from scripts.db import create_db, get_connection


@pytest.fixture
def db_path(tmp_path):
    p = str(tmp_path / "test.db")
    create_db(p)
    return p


@pytest.fixture
def con(db_path):
    c = get_connection(db_path)
    yield c
    c.close()
```

- [ ] **Step 6: Write a quick type smoke-test**

```python
# tests/pipeline/test_types.py
from scripts.pipeline.types import ShallowJob, HermesResult


def test_shallow_job_dedup_key():
    j = ShallowJob(
        provider="gh", title="SWE", company="Acme", url="http://x", location="Remote",
        country="DE", dedup_key="Acme::SWE", posting_date=None, salary_raw=None,
    )
    assert j.dedup_key == "Acme::SWE"


def test_hermes_result_fields():
    r = HermesResult(success=True, data={"status": "success"}, error=None, raw_output="{}")
    assert r.success is True
```

- [ ] **Step 7: Run smoke test**

```bash
cd /Users/zall/interviews
python -m pytest tests/pipeline/test_types.py -v
```
Expected: 2 PASS.

- [ ] **Step 8: Commit**

```bash
git add scripts/__init__.py scripts/pipeline/ scripts/providers/ tests/
git commit -m "feat: add pipeline/types.py, shared auth_check, job_filter, package structure"
```

---

## Chunk 2: Pipeline Modules

### Task 3: `pipeline/hermes.py`

**Files:**
- Create: `scripts/pipeline/hermes.py`
- Create: `tests/fixtures/hermes/*.json`
- Create: `tests/pipeline/test_hermes.py`

- [ ] **Step 1: Create fixture JSON files**

`tests/fixtures/hermes/enrich_success.json`:
```json
{"status": "success", "title": "Senior Engineer", "description": "Build distributed systems.", "apply_url": "https://co.com/apply", "salary_range": "90-120K EUR", "date_posted": "2026-05-10"}
```

`tests/fixtures/hermes/enrich_failure.json`:
```json
{"status": "failure", "error": "login wall"}
```

`tests/fixtures/hermes/sanity_pass.json`:
```json
{"status": "success", "verdict": "pass", "reason": "Remote senior backend, matches profile"}
```

`tests/fixtures/hermes/sanity_skip.json`:
```json
{"status": "success", "verdict": "skip", "reason": "On-site only, Berlin office required"}
```

`tests/fixtures/hermes/sanity_failure.json`:
```json
{"status": "failure", "error": "could not load job description"}
```

- [ ] **Step 2: Write failing tests for `hermes_call()`**

```python
# tests/pipeline/test_hermes.py
from __future__ import annotations
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

FIXTURES = Path(__file__).parent.parent / "fixtures" / "hermes"


def _load(name: str) -> str:
    return (FIXTURES / name).read_text()


@patch("scripts.pipeline.hermes.AIAgent")
def test_success(mock_cls):
    raw = _load("enrich_success.json")
    mock_cls.return_value.chat.return_value = raw
    from scripts.pipeline.hermes import hermes_call
    result = hermes_call("enrich-job", {"job_id": 1, "url": "https://x.com"})
    assert result.success is True
    assert result.data["title"] == "Senior Engineer"
    assert result.error is None


@patch("scripts.pipeline.hermes.AIAgent")
def test_failure_json(mock_cls):
    raw = _load("enrich_failure.json")
    mock_cls.return_value.chat.return_value = raw
    from scripts.pipeline.hermes import hermes_call
    result = hermes_call("enrich-job", {"job_id": 1, "url": "https://x.com"})
    assert result.success is False
    assert result.error == "login wall"


@patch("scripts.pipeline.hermes.AIAgent")
def test_exception_returns_failure(mock_cls):
    mock_cls.return_value.chat.side_effect = RuntimeError("boom")
    from scripts.pipeline.hermes import hermes_call
    result = hermes_call("enrich-job", {"job_id": 1, "url": "https://x.com"})
    assert result.success is False
    assert "boom" in result.error


@patch("scripts.pipeline.hermes.AIAgent")
def test_timeout_returns_failure(mock_cls):
    from concurrent.futures import TimeoutError as FTE
    mock_cls.return_value.chat.side_effect = FTE()
    from scripts.pipeline.hermes import hermes_call
    result = hermes_call("enrich-job", {"job_id": 1, "url": "https://x.com"}, timeout_sec=1)
    assert result.success is False
    assert "timeout" in result.error


@patch("scripts.pipeline.hermes.AIAgent")
def test_unparseable_json(mock_cls):
    mock_cls.return_value.chat.return_value = "no json here"
    from scripts.pipeline.hermes import hermes_call
    result = hermes_call("enrich-job", {"job_id": 1, "url": "https://x.com"})
    assert result.success is False
    assert "parse error" in result.error


def test_build_prompt():
    from scripts.pipeline.hermes import build_prompt
    p = build_prompt("enrich-job", {"job_id": 42, "url": "https://x.com"})
    assert p == "Use skill enrich-job. job_id: 42. url: https://x.com"
```

- [ ] **Step 3: Run tests — confirm they fail**

```bash
python -m pytest tests/pipeline/test_hermes.py -v
```
Expected: FAIL — module not found.

- [ ] **Step 4: Create `scripts/pipeline/hermes.py`**

```python
from __future__ import annotations
import json
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeoutError
from pathlib import Path

from .types import HermesResult

PROJECT_ROOT = Path(__file__).parent.parent.parent
CV_PATH = PROJECT_ROOT / "cv_master_content.md"


def build_prompt(skill: str, context: dict) -> str:
    parts = [f"Use skill {skill}."]
    for k, v in context.items():
        parts.append(f"{k}: {v}")
    return " ".join(parts)


def hermes_call(skill: str, context: dict, timeout_sec: int = 300) -> HermesResult:
    from run_agent import AIAgent  # Hermes Python library — import at call time

    prompt = build_prompt(skill, context)
    try:
        agent = AIAgent(quiet_mode=True, skip_context_files=True, max_iterations=10)
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(agent.chat, prompt)
            raw = future.result(timeout=timeout_sec)
    except FuturesTimeoutError:
        return HermesResult(
            success=False, data={}, error=f"timeout after {timeout_sec}s", raw_output=""
        )
    except Exception as e:
        return HermesResult(success=False, data={}, error=str(e), raw_output="")

    try:
        s = raw
        data = json.loads(s[s.index("{") : s.rindex("}") + 1])
        success = data.get("status") == "success"
        return HermesResult(
            success=success, data=data, error=data.get("error"), raw_output=raw
        )
    except Exception as e:
        return HermesResult(
            success=False, data={}, error=f"parse error: {e}", raw_output=raw
        )
```

- [ ] **Step 5: Run tests — all pass**

```bash
python -m pytest tests/pipeline/test_hermes.py -v
```
Expected: 6 PASS.

- [ ] **Step 6: Commit**

```bash
git add scripts/pipeline/hermes.py tests/pipeline/test_hermes.py tests/fixtures/hermes/
git commit -m "feat: add pipeline/hermes.py with hermes_call() + tests"
```

---

### Task 4: `pipeline/dedup.py`

**Files:**
- Create: `scripts/pipeline/dedup.py`
- Create: `tests/pipeline/test_dedup.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/pipeline/test_dedup.py
import pytest
from scripts.pipeline.types import ShallowJob
from scripts.pipeline.dedup import dedup_jobs
from scripts.db import get_connection


def _job(company="Acme", title="SWE", url="http://x.com"):
    return ShallowJob(
        provider="test", title=title, company=company, url=url,
        location="Remote", country="DE",
        dedup_key=f"{company}::{title}",
        posting_date=None, salary_raw=None,
    )


def test_all_new_pass_through(db_path):
    jobs = [_job("A", "E1"), _job("B", "E2")]
    result = dedup_jobs(jobs, db_path=db_path)
    assert len(result) == 2


def test_existing_dedup_key_filtered(db_path, con):
    con.execute(
        "INSERT INTO jobs (url, provider, dedup_key) VALUES ('http://old.com', 't', 'Acme::SWE')"
    )
    con.commit()
    con.close()
    jobs = [_job("Acme", "SWE", "http://new.com")]
    result = dedup_jobs(jobs, db_path=db_path)
    assert result == []


def test_mixed_new_and_existing(db_path, con):
    con.execute(
        "INSERT INTO jobs (url, provider, dedup_key) VALUES ('http://x.com', 't', 'Acme::SWE')"
    )
    con.commit()
    con.close()
    jobs = [_job("Acme", "SWE"), _job("Beta", "Dev", "http://y.com")]
    result = dedup_jobs(jobs, db_path=db_path)
    assert len(result) == 1
    assert result[0].company == "Beta"


def test_empty_input(db_path):
    assert dedup_jobs([], db_path=db_path) == []
```

- [ ] **Step 2: Run tests to confirm failure**

```bash
python -m pytest tests/pipeline/test_dedup.py -v
```
Expected: FAIL.

- [ ] **Step 3: Create `scripts/pipeline/dedup.py`**

```python
from __future__ import annotations
import sqlite3
from pathlib import Path

from .types import ShallowJob

_PROJECT_ROOT = Path(__file__).parent.parent.parent
_DEFAULT_DB = str(_PROJECT_ROOT / "jobs.db")


def dedup_jobs(jobs: list[ShallowJob], db_path: str = _DEFAULT_DB) -> list[ShallowJob]:
    if not jobs:
        return []
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    try:
        keys = [j.dedup_key for j in jobs]
        placeholders = ",".join("?" * len(keys))
        existing = {
            row[0]
            for row in con.execute(
                f"SELECT dedup_key FROM jobs WHERE dedup_key IN ({placeholders})", keys
            ).fetchall()
        }
    finally:
        con.close()
    return [j for j in jobs if j.dedup_key not in existing]
```

- [ ] **Step 4: Run tests — all pass**

```bash
python -m pytest tests/pipeline/test_dedup.py -v
```

- [ ] **Step 5: Commit**

```bash
git add scripts/pipeline/dedup.py tests/pipeline/test_dedup.py
git commit -m "feat: add pipeline/dedup.py — dedup_jobs() filters existing dedup_keys"
```

---

### Task 5: `pipeline/ingest.py`

**Files:**
- Create: `scripts/pipeline/ingest.py`
- Create: `tests/pipeline/test_ingest.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/pipeline/test_ingest.py
import sqlite3
from scripts.pipeline.types import ShallowJob
from scripts.pipeline.ingest import ingest_jobs
from scripts.db import get_connection


def _job(url="http://x.com", company="Acme", title="SWE"):
    return ShallowJob(
        provider="greenhouse", title=title, company=company, url=url,
        location="Remote", country="DE",
        dedup_key=f"{company}::{title}",
        posting_date="2026-05-01", salary_raw="90K EUR",
    )


def test_ingest_returns_ids(db_path):
    jobs = [_job("http://a.com", "A", "E1"), _job("http://b.com", "B", "E2")]
    ids = ingest_jobs(jobs, db_path=db_path)
    assert len(ids) == 2
    assert all(isinstance(i, int) for i in ids)


def test_ingest_sets_status_listed(db_path, con):
    ids = ingest_jobs([_job()], db_path=db_path)
    row = con.execute("SELECT status, dedup_key FROM jobs WHERE id = ?", (ids[0],)).fetchone()
    assert row["status"] == "listed"
    assert row["dedup_key"] == "Acme::SWE"


def test_ingest_stores_all_fields(db_path, con):
    ids = ingest_jobs([_job()], db_path=db_path)
    row = con.execute("SELECT * FROM jobs WHERE id = ?", (ids[0],)).fetchone()
    assert row["provider"] == "greenhouse"
    assert row["posted_company_name"] == "Acme"
    assert row["title"] == "SWE"
    assert row["date_posted"] == "2026-05-01"
    assert row["salary_range"] == "90K EUR"


def test_ingest_empty_list(db_path):
    ids = ingest_jobs([], db_path=db_path)
    assert ids == []
```

- [ ] **Step 2: Run failing**

```bash
python -m pytest tests/pipeline/test_ingest.py -v
```

- [ ] **Step 3: Create `scripts/pipeline/ingest.py`**

```python
from __future__ import annotations
import sqlite3
from pathlib import Path

from .types import ShallowJob

_DEFAULT_DB = str(Path(__file__).parent.parent.parent / "jobs.db")


def ingest_jobs(jobs: list[ShallowJob], db_path: str = _DEFAULT_DB) -> list[int]:
    if not jobs:
        return []
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    ids: list[int] = []
    try:
        for j in jobs:
            cur = con.execute(
                """INSERT INTO jobs
                   (url, provider, posted_company_name, title, location, country,
                    date_posted, salary_range, dedup_key, status)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'listed')""",
                (j.url, j.provider, j.company, j.title, j.location, j.country,
                 j.posting_date, j.salary_raw, j.dedup_key),
            )
            ids.append(cur.lastrowid)
        con.commit()
    finally:
        con.close()
    return ids
```

- [ ] **Step 4: Run — all pass**

```bash
python -m pytest tests/pipeline/test_ingest.py -v
```

- [ ] **Step 5: Commit**

```bash
git add scripts/pipeline/ingest.py tests/pipeline/test_ingest.py
git commit -m "feat: add pipeline/ingest.py — ingest_jobs() inserts with status=listed"
```

---

### Task 6: Skills + `pipeline/enrich_job.py`

**Files:**
- Create: `scripts/skills/enrich-job/SKILL.md`
- Create: `scripts/pipeline/enrich_job.py`
- Create: `tests/pipeline/test_enrich_job.py`

- [ ] **Step 1: Create `scripts/skills/enrich-job/SKILL.md`**

```markdown
# enrich-job

Enrich a job listing by visiting its URL and extracting structured data.

## Input

You will receive a prompt like:
`Use skill enrich-job. job_id: 42. url: https://boards.greenhouse.io/company/jobs/123. cv_path: /path/to/cv.md`

## Task

1. Open the URL using your browser tools
2. Extract the following fields from the job page:
   - title (job title, exact)
   - description (full job description, max 2000 chars)
   - apply_url (the direct application URL, if different from listing URL)
   - salary_range (salary range as shown, e.g. "90-120K EUR"; null if not shown)
   - date_posted (ISO date YYYY-MM-DD if available; null otherwise)

## Output

Respond with a single JSON block. No prose before or after.

Success:
```json
{"status": "success", "title": "Senior Backend Engineer", "description": "...", "apply_url": "https://...", "salary_range": "90-120K EUR", "date_posted": "2026-05-10"}
```

Failure (login wall, 404, extraction error):
```json
{"status": "failure", "error": "login wall"}
```

## Rules
- If the page requires login, return failure with error="login wall"
- If the page returns 404/not found, return failure with error="page not found"
- If you can't extract meaningful description (< 100 chars), return failure with error="extraction failed"
- apply_url defaults to the input url if no separate apply link is found
- Do NOT include CV content in the output
```

- [ ] **Step 2: Write failing tests for `enrich_job()`**

```python
# tests/pipeline/test_enrich_job.py
from unittest.mock import patch, MagicMock
from scripts.pipeline.types import HermesResult
from scripts.db import get_connection


def _insert_job(con, url="http://x.com"):
    jid = con.execute(
        "INSERT INTO jobs (url, provider, status) VALUES (?, 'gh', 'listed')", (url,)
    ).lastrowid
    con.commit()
    return jid


@patch("scripts.pipeline.enrich_job.hermes_call")
def test_success_updates_db(mock_hermes, db_path, con):
    mock_hermes.return_value = HermesResult(
        success=True,
        data={"status": "success", "title": "SWE", "description": "Build things.",
              "apply_url": "http://x.com/apply", "salary_range": "100K EUR",
              "date_posted": "2026-05-01"},
        error=None, raw_output="",
    )
    jid = _insert_job(con)
    from scripts.pipeline.enrich_job import enrich_job
    result = enrich_job(jid, db_path=db_path)
    assert result.success is True
    row = con.execute("SELECT * FROM jobs WHERE id = ?", (jid,)).fetchone()
    assert row["status"] == "new"
    assert row["title"] == "SWE"
    assert row["description"] == "Build things."
    assert row["salary_range"] == "100K EUR"


@patch("scripts.pipeline.enrich_job.hermes_call")
def test_failure_sets_enrich_failed(mock_hermes, db_path, con):
    mock_hermes.return_value = HermesResult(
        success=False, data={}, error="login wall", raw_output="",
    )
    jid = _insert_job(con)
    from scripts.pipeline.enrich_job import enrich_job
    result = enrich_job(jid, db_path=db_path)
    assert result.success is False
    row = con.execute("SELECT status, comment FROM jobs WHERE id = ?", (jid,)).fetchone()
    assert row["status"] == "enrich_failed"
    assert row["comment"] == "login wall"


@patch("scripts.pipeline.enrich_job.hermes_call")
def test_hermes_context_includes_url_and_cv(mock_hermes, db_path, con):
    mock_hermes.return_value = HermesResult(
        success=False, data={}, error="x", raw_output=""
    )
    jid = _insert_job(con, url="http://job.com")
    from scripts.pipeline.enrich_job import enrich_job
    enrich_job(jid, db_path=db_path)
    call_args = mock_hermes.call_args
    assert call_args[0][0] == "enrich-job"
    ctx = call_args[0][1]
    assert ctx["job_id"] == jid
    assert ctx["url"] == "http://job.com"
    assert "cv_path" in ctx
```

- [ ] **Step 3: Run failing**

```bash
python -m pytest tests/pipeline/test_enrich_job.py -v
```

- [ ] **Step 4: Create `scripts/pipeline/enrich_job.py`**

```python
from __future__ import annotations
import sqlite3
from pathlib import Path

from .hermes import hermes_call, CV_PATH
from .types import HermesResult
from scripts.db import get_connection, update_job_status

_DEFAULT_DB = str(Path(__file__).parent.parent.parent / "jobs.db")


def enrich_job(job_id: int, db_path: str = _DEFAULT_DB) -> HermesResult:
    con = get_connection(db_path)
    try:
        job = con.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        if job is None:
            return HermesResult(
                success=False, data={}, error=f"job {job_id} not found", raw_output=""
            )
        result = hermes_call(
            "enrich-job",
            {"job_id": job_id, "url": job["url"], "cv_path": str(CV_PATH)},
        )
        if result.success:
            d = result.data
            con.execute(
                """UPDATE jobs SET title = COALESCE(?, title),
                   description = ?, apply_url = ?, salary_range = COALESCE(?, salary_range),
                   date_posted = COALESCE(?, date_posted),
                   status = 'new', updated_at = datetime('now')
                   WHERE id = ?""",
                (d.get("title"), d.get("description"), d.get("apply_url"),
                 d.get("salary_range"), d.get("date_posted"), job_id),
            )
        else:
            update_job_status(con, job_id, "enrich_failed", comment=result.error)
        con.commit()
    finally:
        con.close()
    return result
```

- [ ] **Step 5: Run — all pass**

```bash
python -m pytest tests/pipeline/test_enrich_job.py -v
```

- [ ] **Step 6: Commit**

```bash
git add scripts/pipeline/enrich_job.py scripts/skills/enrich-job/ tests/pipeline/test_enrich_job.py
git commit -m "feat: add enrich_job pipeline step + enrich-job skill"
```

---

### Task 7: Skills + `pipeline/sanity_check_job.py` + `pipeline/notify.py`

**Files:**
- Create: `scripts/skills/sanity-check-job/SKILL.md`
- Create: `scripts/pipeline/sanity_check_job.py`
- Create: `scripts/pipeline/notify.py`
- Create: `tests/pipeline/test_sanity_check_job.py`
- Create: `tests/pipeline/test_notify.py`

- [ ] **Step 1: Create `scripts/skills/sanity-check-job/SKILL.md`**

```markdown
# sanity-check-job

Quickly filter a job against the candidate's profile before deep research.

## Input

`Use skill sanity-check-job. job_id: 42. cv_path: /path/to/cv.md`

## Task

1. Read the CV from cv_path
2. Read the job from the database using the job_id (use your DB read tools)
3. Check ONLY these hard disqualifiers:
   - Requires physical on-site presence (not remote-eligible)
   - Requires relocation to a location not in the candidate's target list (Berlin, Spain, or EU remote)
   - Junior/entry-level role (candidate is senior/principal level)
   - Completely unrelated domain (e.g. hardware, medical, legal)
4. If none apply: verdict = "pass"
5. If any apply: verdict = "skip" with the specific reason

## Output

Respond with a single JSON block. No prose.

Pass:
```json
{"status": "success", "verdict": "pass", "reason": "Remote senior backend role, matches profile"}
```

Skip:
```json
{"status": "success", "verdict": "skip", "reason": "On-site only, Berlin office required"}
```

Failure (cannot read job or CV):
```json
{"status": "failure", "error": "could not load job description"}
```

## Rules
- verdict is always "pass" or "skip" when status="success"
- Do NOT apply subjective judgements — only hard disqualifiers listed above
- A job with "hybrid" or unclear remote policy should pass (not skip)
```

- [ ] **Step 2: Write failing tests for `sanity_check_job()`**

```python
# tests/pipeline/test_sanity_check_job.py
from unittest.mock import patch
from scripts.pipeline.types import HermesResult
from scripts.db import get_connection


def _insert_job(con, status="new"):
    jid = con.execute(
        "INSERT INTO jobs (url, provider, status) VALUES ('http://x.com','gh',?)", (status,)
    ).lastrowid
    con.commit()
    return jid


@patch("scripts.pipeline.sanity_check_job.hermes_call")
def test_pass_leaves_status_new(mock_hermes, db_path, con):
    mock_hermes.return_value = HermesResult(
        success=True, data={"status": "success", "verdict": "pass", "reason": "Good fit"},
        error=None, raw_output="",
    )
    jid = _insert_job(con)
    from scripts.pipeline.sanity_check_job import sanity_check_job
    result = sanity_check_job(jid, db_path=db_path)
    assert result.success is True
    row = con.execute("SELECT status FROM jobs WHERE id = ?", (jid,)).fetchone()
    assert row["status"] == "new"


@patch("scripts.pipeline.sanity_check_job.hermes_call")
def test_skip_sets_not_interested(mock_hermes, db_path, con):
    mock_hermes.return_value = HermesResult(
        success=True,
        data={"status": "success", "verdict": "skip", "reason": "On-site only"},
        error=None, raw_output="",
    )
    jid = _insert_job(con)
    from scripts.pipeline.sanity_check_job import sanity_check_job
    sanity_check_job(jid, db_path=db_path)
    row = con.execute("SELECT status, comment FROM jobs WHERE id = ?", (jid,)).fetchone()
    assert row["status"] == "not_interested"
    assert row["comment"] == "On-site only"


@patch("scripts.pipeline.sanity_check_job.hermes_call")
def test_hermes_failure_sets_sanity_failed(mock_hermes, db_path, con):
    mock_hermes.return_value = HermesResult(
        success=False, data={}, error="could not load job description", raw_output="",
    )
    jid = _insert_job(con)
    from scripts.pipeline.sanity_check_job import sanity_check_job
    sanity_check_job(jid, db_path=db_path)
    row = con.execute("SELECT status FROM jobs WHERE id = ?", (jid,)).fetchone()
    assert row["status"] == "sanity_failed"
```

- [ ] **Step 3: Run failing**

```bash
python -m pytest tests/pipeline/test_sanity_check_job.py -v
```

- [ ] **Step 4: Create `scripts/pipeline/sanity_check_job.py`**

```python
from __future__ import annotations
from pathlib import Path

from .hermes import hermes_call, CV_PATH
from .types import HermesResult
from scripts.db import get_connection, update_job_status

_DEFAULT_DB = str(Path(__file__).parent.parent.parent / "jobs.db")


def sanity_check_job(job_id: int, db_path: str = _DEFAULT_DB) -> HermesResult:
    con = get_connection(db_path)
    try:
        result = hermes_call(
            "sanity-check-job",
            {"job_id": job_id, "cv_path": str(CV_PATH)},
        )
        if result.success:
            if result.data.get("verdict") == "skip":
                update_job_status(
                    con, job_id, "not_interested",
                    comment=result.data.get("reason"),
                )
                con.commit()
            # verdict=pass: no status change needed
        else:
            update_job_status(con, job_id, "sanity_failed", comment=result.error)
            con.commit()
    finally:
        con.close()
    return result
```

- [ ] **Step 5: Run — all pass**

```bash
python -m pytest tests/pipeline/test_sanity_check_job.py -v
```

- [ ] **Step 6: Write failing test for `notify.py`**

```python
# tests/pipeline/test_notify.py
from unittest.mock import patch


@patch("scripts.pipeline.notify.telegram_notify")
def test_send_digest_no_failures(mock_tg):
    from scripts.pipeline.notify import send_daily_digest
    send_daily_digest()
    mock_tg.assert_not_called()


@patch("scripts.pipeline.notify.telegram_notify")
def test_send_digest_with_failures(mock_tg):
    from scripts.pipeline.notify import send_daily_digest
    send_daily_digest(
        enrich_failures=[(1, "timeout"), (2, "login wall")],
        sanity_failures=[(3, "error")],
    )
    mock_tg.assert_called_once()
    msg = mock_tg.call_args[0][0]
    assert "enrich" in msg.lower()
    assert "sanity" in msg.lower()
    assert "2" in msg
```

- [ ] **Step 7: Create `scripts/pipeline/notify.py`**

```python
from __future__ import annotations
import subprocess

HERMES = "/Users/zall/.local/bin/hermes"
TELEGRAM_TARGET = "telegram"


def telegram_notify(message: str) -> None:
    subprocess.run(
        [HERMES, "send", "--to", TELEGRAM_TARGET, message],
        capture_output=True,
    )


def send_daily_digest(
    enrich_failures: list[tuple[int, str]] | None = None,
    sanity_failures: list[tuple[int, str]] | None = None,
) -> None:
    enrich_failures = enrich_failures or []
    sanity_failures = sanity_failures or []
    if not enrich_failures and not sanity_failures:
        return
    lines = ["⚠️ Pipeline completed with failures"]
    if enrich_failures:
        lines.append(f"Enrich failed: {len(enrich_failures)} job(s)")
        for jid, err in enrich_failures[:5]:
            lines.append(f"  • job {jid}: {err[:60]}")
    if sanity_failures:
        lines.append(f"Sanity check failed: {len(sanity_failures)} job(s)")
        for jid, err in sanity_failures[:5]:
            lines.append(f"  • job {jid}: {err[:60]}")
    telegram_notify("\n".join(lines))
```

- [ ] **Step 8: Run all pipeline tests**

```bash
python -m pytest tests/pipeline/ -v
```
Expected: all PASS.

- [ ] **Step 9: Commit**

```bash
git add scripts/pipeline/sanity_check_job.py scripts/pipeline/notify.py \
        scripts/skills/sanity-check-job/ \
        tests/pipeline/test_sanity_check_job.py tests/pipeline/test_notify.py
git commit -m "feat: add sanity_check_job, notify pipeline steps + sanity-check-job skill"
```

---

## Chunk 3: Providers

### Task 8: Greenhouse provider

**Files:**
- Create: `scripts/providers/greenhouse/__init__.py`
- Create: `scripts/providers/greenhouse/check_auth.py`
- Create: `scripts/providers/greenhouse/scrape_jobs.py`
- Create: `tests/providers/greenhouse/__init__.py`
- Create: `tests/providers/greenhouse/test_check_auth.py`
- Create: `tests/providers/greenhouse/test_scrape_jobs.py`
- Create: `tests/fixtures/greenhouse/scrape_output.json`

- [ ] **Step 1: Create fixture `tests/fixtures/greenhouse/scrape_output.json`**

```json
[
  {
    "provider": "greenhouse",
    "company": "Acme Corp",
    "title": "Senior Backend Engineer",
    "url": "https://acme.greenhouse.io/jobs/123",
    "description": "",
    "applyUrl": "https://acme.greenhouse.io/jobs/123",
    "location": "Remote",
    "country": "Germany",
    "postingDate": "",
    "searchLabel": "Berlin Remote"
  }
]
```

- [ ] **Step 2: Write failing tests**

```python
# tests/providers/greenhouse/test_check_auth.py
from unittest.mock import MagicMock, patch


@patch("scripts.providers.greenhouse.check_auth.sync_playwright")
def test_already_authenticated(mock_pw):
    page = MagicMock()
    page.url = "https://my.greenhouse.io/jobs"  # not the sign-in page
    ctx = MagicMock()
    ctx.new_page.return_value = page
    browser = MagicMock()
    browser.contexts = [ctx]
    mock_pw.return_value.__enter__.return_value.chromium.connect_over_cdp.return_value = browser

    from scripts.providers.greenhouse.check_auth import check_auth
    check_auth("http://localhost:9222")  # should not raise


@patch("scripts.providers.greenhouse.check_auth.sync_playwright")
@patch("scripts.providers.greenhouse.check_auth.wait_for_auth")
def test_auth_required_raises_on_timeout(mock_wait, mock_pw):
    page = MagicMock()
    page.url = "https://my.greenhouse.io/users/sign_in"
    ctx = MagicMock()
    ctx.new_page.return_value = page
    browser = MagicMock()
    browser.contexts = [ctx]
    mock_pw.return_value.__enter__.return_value.chromium.connect_over_cdp.return_value = browser
    mock_wait.return_value = False  # timeout

    from scripts.providers.greenhouse.check_auth import check_auth, AuthError
    import pytest
    with pytest.raises(AuthError):
        check_auth("http://localhost:9222")
```

```python
# tests/providers/greenhouse/test_scrape_jobs.py
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

FIXTURE = Path(__file__).parent.parent.parent / "fixtures" / "greenhouse" / "scrape_output.json"


@patch("scripts.providers.greenhouse.scrape_jobs.collect_greenhouse")
@patch("scripts.providers.greenhouse.scrape_jobs.sync_playwright")
def test_returns_shallow_jobs(mock_pw, mock_collect):
    mock_collect.return_value = json.loads(FIXTURE.read_text())
    page = MagicMock()
    ctx = MagicMock(); ctx.new_page.return_value = page
    browser = MagicMock(); browser.contexts = [ctx]
    mock_pw.return_value.__enter__.return_value.chromium.connect_over_cdp.return_value = browser

    from scripts.providers.greenhouse.scrape_jobs import scrape_jobs
    jobs = scrape_jobs("berlin", "http://localhost:9222")
    assert len(jobs) == 1
    assert jobs[0].company == "Acme Corp"
    assert jobs[0].title == "Senior Backend Engineer"
    assert jobs[0].dedup_key == "Acme Corp::Senior Backend Engineer"
    assert jobs[0].provider == "greenhouse"


@patch("scripts.providers.greenhouse.scrape_jobs.collect_greenhouse")
@patch("scripts.providers.greenhouse.scrape_jobs.sync_playwright")
def test_irrelevant_jobs_filtered(mock_pw, mock_collect):
    mock_collect.return_value = [
        {"provider": "greenhouse", "company": "X", "title": "Sales Manager",
         "url": "http://x.com", "location": "Remote", "country": "DE",
         "postingDate": "", "applyUrl": "", "salaryRaw": ""}
    ]
    page = MagicMock()
    ctx = MagicMock(); ctx.new_page.return_value = page
    browser = MagicMock(); browser.contexts = [ctx]
    mock_pw.return_value.__enter__.return_value.chromium.connect_over_cdp.return_value = browser

    from scripts.providers.greenhouse.scrape_jobs import scrape_jobs
    jobs = scrape_jobs("berlin", "http://localhost:9222")
    assert jobs == []
```

- [ ] **Step 3: Run failing**

```bash
python -m pytest tests/providers/greenhouse/ -v
```

- [ ] **Step 4: Create `scripts/providers/greenhouse/check_auth.py`**

```python
from __future__ import annotations
from playwright.sync_api import sync_playwright

from scripts.providers._shared.auth_check import wait_for_auth

CHECK_URL = "https://my.greenhouse.io/jobs"


class AuthError(Exception):
    pass


def _is_auth_page(url: str) -> bool:
    return "/users/sign_in" in url


def check_auth(cdp_url: str) -> None:
    """Raises AuthError if Greenhouse session cannot be established."""
    with sync_playwright() as pw:
        browser = pw.chromium.connect_over_cdp(cdp_url)
        ctx = browser.contexts[0]
        page = ctx.new_page()
        try:
            ok = wait_for_auth(page, "greenhouse", CHECK_URL, _is_auth_page)
        finally:
            browser.close()
    if not ok:
        raise AuthError("Greenhouse auth timed out")
```

- [ ] **Step 5: Create `scripts/providers/greenhouse/scrape_jobs.py`**

Extract list-collection logic from `scripts/scrape_greenhouse.py` (`collect_greenhouse` function), adapt to return `list[ShallowJob]`:

```python
from __future__ import annotations
from playwright.sync_api import sync_playwright

from scripts.pipeline.types import ShallowJob
from scripts.providers._shared.job_filter import is_relevant
from scripts.scrape_greenhouse import (
    LOCATION_PRESETS, build_feed_url, build_title_url, collect_greenhouse,
)

DEFAULT_TITLES: list[str] = []  # use personalised feed by default


def scrape_jobs(location: str, cdp_url: str) -> list[ShallowJob]:
    preset_key = location.lower()
    if preset_key not in LOCATION_PRESETS:
        raise ValueError(f"Unknown location preset: {location!r}")
    preset = LOCATION_PRESETS[preset_key]
    search = {
        "label": f"{location.title()} Remote",
        "query": "",
        "country": preset["country"],
        "locationLabel": f"{location.title()} Remote",
        "url": build_feed_url(preset),
    }

    raw_rows: list[dict] = []
    with sync_playwright() as pw:
        browser = pw.chromium.connect_over_cdp(cdp_url)
        ctx = browser.contexts[0]
        page = ctx.new_page()
        try:
            raw_rows = collect_greenhouse(page, search)
        finally:
            browser.close()

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
    return jobs
```

- [ ] **Step 6: Run — all pass**

```bash
python -m pytest tests/providers/greenhouse/ -v
```

- [ ] **Step 7: Commit**

```bash
git add scripts/providers/greenhouse/ tests/providers/greenhouse/ tests/fixtures/greenhouse/
git commit -m "feat: add greenhouse provider (check_auth, scrape_jobs) + tests"
```

---

### Task 9: JobLeads provider

**Files:**
- Create: `scripts/providers/jobleads/__init__.py`
- Create: `scripts/providers/jobleads/check_auth.py`
- Create: `scripts/providers/jobleads/scrape_jobs.py`
- Create: `tests/providers/jobleads/__init__.py`
- Create: `tests/providers/jobleads/test_check_auth.py`
- Create: `tests/providers/jobleads/test_scrape_jobs.py`
- Create: `tests/fixtures/jobleads/scrape_output.json`

- [ ] **Step 1: Create fixture `tests/fixtures/jobleads/scrape_output.json`**

```json
[
  {
    "provider": "jobleads",
    "company": "Beta GmbH",
    "title": "Senior Software Engineer",
    "url": "https://www.jobleads.com/job/beta-swe-456",
    "location": "Remote",
    "country": "Germany",
    "postedRelative": "3 days ago",
    "salaryRaw": "€80,000 - €100,000"
  }
]
```

- [ ] **Step 2: Write failing tests**

```python
# tests/providers/jobleads/test_check_auth.py
from unittest.mock import MagicMock, patch
import pytest


@patch("scripts.providers.jobleads.check_auth.sync_playwright")
def test_already_authenticated(mock_pw):
    page = MagicMock()
    page.url = "https://www.jobleads.com/search/jobs"
    ctx = MagicMock(); ctx.new_page.return_value = page
    browser = MagicMock(); browser.contexts = [ctx]
    mock_pw.return_value.__enter__.return_value.chromium.connect_over_cdp.return_value = browser
    from scripts.providers.jobleads.check_auth import check_auth
    check_auth("http://localhost:9222")  # no raise


@patch("scripts.providers.jobleads.check_auth.sync_playwright")
@patch("scripts.providers.jobleads.check_auth.wait_for_auth")
def test_timeout_raises(mock_wait, mock_pw):
    page = MagicMock()
    page.url = "https://www.jobleads.com/external-home"
    ctx = MagicMock(); ctx.new_page.return_value = page
    browser = MagicMock(); browser.contexts = [ctx]
    mock_pw.return_value.__enter__.return_value.chromium.connect_over_cdp.return_value = browser
    mock_wait.return_value = False
    from scripts.providers.jobleads.check_auth import check_auth, AuthError
    with pytest.raises(AuthError):
        check_auth("http://localhost:9222")
```

```python
# tests/providers/jobleads/test_scrape_jobs.py
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

FIXTURE = Path(__file__).parent.parent.parent / "fixtures" / "jobleads" / "scrape_output.json"


@patch("scripts.providers.jobleads.scrape_jobs.collect_jobleads")
@patch("scripts.providers.jobleads.scrape_jobs.sync_playwright")
def test_returns_shallow_jobs(mock_pw, mock_collect):
    mock_collect.return_value = json.loads(FIXTURE.read_text())
    page = MagicMock()
    ctx = MagicMock(); ctx.new_page.return_value = page
    browser = MagicMock(); browser.contexts = [ctx]
    mock_pw.return_value.__enter__.return_value.chromium.connect_over_cdp.return_value = browser

    from scripts.providers.jobleads.scrape_jobs import scrape_jobs
    jobs = scrape_jobs("berlin", "http://localhost:9222")
    assert len(jobs) == 1
    assert jobs[0].company == "Beta GmbH"
    assert jobs[0].dedup_key == "Beta GmbH::Senior Software Engineer"
    assert jobs[0].provider == "jobleads"
```

- [ ] **Step 3: Create `scripts/providers/jobleads/check_auth.py`**

```python
from __future__ import annotations
import re
from playwright.sync_api import sync_playwright
from scripts.providers._shared.auth_check import wait_for_auth

CHECK_URL = "https://www.jobleads.com/search/jobs"


class AuthError(Exception):
    pass


def _is_auth_page(url: str) -> bool:
    return bool(re.search(r"/external-home|accounts\.google\.com|modal=login|sign.in", url))


def check_auth(cdp_url: str) -> None:
    with sync_playwright() as pw:
        browser = pw.chromium.connect_over_cdp(cdp_url)
        ctx = browser.contexts[0]
        page = ctx.new_page()
        try:
            ok = wait_for_auth(page, "jobleads", CHECK_URL, _is_auth_page)
        finally:
            browser.close()
    if not ok:
        raise AuthError("JobLeads auth timed out")
```

- [ ] **Step 4: Create `scripts/providers/jobleads/scrape_jobs.py`**

```python
from __future__ import annotations
from playwright.sync_api import sync_playwright

from scripts.pipeline.types import ShallowJob
from scripts.providers._shared.job_filter import is_relevant
from scripts.scrape_jobleads import (
    LOCATION_PRESETS, build_feed_url, collect_jobleads,
)


def scrape_jobs(location: str, cdp_url: str) -> list[ShallowJob]:
    preset_key = location.lower()
    if preset_key not in LOCATION_PRESETS:
        raise ValueError(f"Unknown location: {location!r}")
    preset = LOCATION_PRESETS[preset_key]
    search = {
        "label": f"{location.title()} Remote",
        "query": "",
        "country": preset["country"],
        "url": build_feed_url(preset),
    }

    raw_rows: list[dict] = []
    with sync_playwright() as pw:
        browser = pw.chromium.connect_over_cdp(cdp_url)
        ctx = browser.contexts[0]
        page = ctx.new_page()
        try:
            raw_rows = collect_jobleads(page, search)
        finally:
            browser.close()

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
            posting_date=None,  # enriched by Hermes
            salary_raw=r.get("salaryRaw") or None,
        )
        if is_relevant({"title": j.title}):
            jobs.append(j)
    return jobs
```

- [ ] **Step 5: Run — all pass**

```bash
python -m pytest tests/providers/jobleads/ -v
```

- [ ] **Step 6: Commit**

```bash
git add scripts/providers/jobleads/ tests/providers/jobleads/ tests/fixtures/jobleads/
git commit -m "feat: add jobleads provider (check_auth, scrape_jobs) + tests"
```

---

### Task 10: Wellfound provider

**Files:**
- Create: `scripts/providers/wellfound/__init__.py`
- Create: `scripts/providers/wellfound/check_auth.py`
- Create: `scripts/providers/wellfound/scrape_jobs.py`
- Create: `tests/providers/wellfound/__init__.py`
- Create: `tests/providers/wellfound/test_check_auth.py`
- Create: `tests/providers/wellfound/test_scrape_jobs.py`
- Create: `tests/fixtures/wellfound/scrape_output.json`

- [ ] **Step 1: Create fixture `tests/fixtures/wellfound/scrape_output.json`**

```json
[
  {
    "provider": "wellfound",
    "company": "StartupX",
    "title": "Staff Software Engineer",
    "url": "https://wellfound.com/jobs/123-staff-swe",
    "applyUrl": "https://wellfound.com/jobs/123-staff-swe",
    "description": "",
    "location": "Remote",
    "country": "Germany",
    "postingDate": "1 week ago",
    "salaryRaw": "$120K - $160K",
    "equityRaw": "0.1% - 0.5%"
  }
]
```

- [ ] **Step 2: Write failing tests**

```python
# tests/providers/wellfound/test_check_auth.py
from unittest.mock import MagicMock, patch
import pytest


@patch("scripts.providers.wellfound.check_auth.sync_playwright")
def test_already_authenticated(mock_pw):
    page = MagicMock()
    page.url = "https://wellfound.com/jobs"
    ctx = MagicMock(); ctx.new_page.return_value = page
    browser = MagicMock(); browser.contexts = [ctx]
    mock_pw.return_value.__enter__.return_value.chromium.connect_over_cdp.return_value = browser
    from scripts.providers.wellfound.check_auth import check_auth
    check_auth("http://localhost:9222")


@patch("scripts.providers.wellfound.check_auth.sync_playwright")
@patch("scripts.providers.wellfound.check_auth.wait_for_auth")
def test_timeout_raises(mock_wait, mock_pw):
    page = MagicMock()
    page.url = "https://wellfound.com/login"
    ctx = MagicMock(); ctx.new_page.return_value = page
    browser = MagicMock(); browser.contexts = [ctx]
    mock_pw.return_value.__enter__.return_value.chromium.connect_over_cdp.return_value = browser
    mock_wait.return_value = False
    from scripts.providers.wellfound.check_auth import check_auth, AuthError
    with pytest.raises(AuthError):
        check_auth("http://localhost:9222")
```

```python
# tests/providers/wellfound/test_scrape_jobs.py
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

FIXTURE = Path(__file__).parent.parent.parent / "fixtures" / "wellfound" / "scrape_output.json"


@patch("scripts.providers.wellfound.scrape_jobs.collect_wellfound")
@patch("scripts.providers.wellfound.scrape_jobs.apply_filters")
@patch("scripts.providers.wellfound.scrape_jobs.change_location")
@patch("scripts.providers.wellfound.scrape_jobs.scroll_to_load_all")
@patch("scripts.providers.wellfound.scrape_jobs.sync_playwright")
def test_returns_shallow_jobs(mock_pw, mock_scroll, mock_loc, mock_filters, mock_collect):
    mock_collect.return_value = json.loads(FIXTURE.read_text())
    page = MagicMock()
    ctx = MagicMock(); ctx.new_page.return_value = page
    browser = MagicMock(); browser.contexts = [ctx]
    mock_pw.return_value.__enter__.return_value.chromium.connect_over_cdp.return_value = browser

    from scripts.providers.wellfound.scrape_jobs import scrape_jobs
    jobs = scrape_jobs("berlin", "http://localhost:9222")
    assert len(jobs) == 1
    assert jobs[0].company == "StartupX"
    assert jobs[0].dedup_key == "StartupX::Staff Software Engineer"
    assert jobs[0].provider == "wellfound"
```

- [ ] **Step 3: Create `scripts/providers/wellfound/check_auth.py`**

```python
from __future__ import annotations
import re
from playwright.sync_api import sync_playwright
from scripts.providers._shared.auth_check import wait_for_auth

CHECK_URL = "https://wellfound.com/jobs"


class AuthError(Exception):
    pass


def _is_auth_page(url: str) -> bool:
    return bool(re.search(r"/login|/signin|sign_in|/auth", url, re.I))


def check_auth(cdp_url: str) -> None:
    with sync_playwright() as pw:
        browser = pw.chromium.connect_over_cdp(cdp_url)
        ctx = browser.contexts[0]
        page = ctx.new_page()
        try:
            ok = wait_for_auth(page, "wellfound", CHECK_URL, _is_auth_page)
        finally:
            browser.close()
    if not ok:
        raise AuthError("Wellfound auth timed out")
```

- [ ] **Step 4: Create `scripts/providers/wellfound/scrape_jobs.py`**

```python
from __future__ import annotations
from playwright.sync_api import sync_playwright

from scripts.pipeline.types import ShallowJob
from scripts.providers._shared.job_filter import is_relevant
from scripts.scrape_wellfound import (
    LOCATION_PRESETS, WELLFOUND_BASE,
    apply_filters, change_location, scroll_to_load_all, collect_wellfound,
)


def scrape_jobs(location: str, cdp_url: str) -> list[ShallowJob]:
    preset_key = location.lower()
    if preset_key not in LOCATION_PRESETS:
        raise ValueError(f"Unknown location: {location!r}")
    country_name = {"berlin": "Germany", "spain": "Spain"}.get(preset_key, location)
    location_query = LOCATION_PRESETS[preset_key]

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
            raw_rows = collect_wellfound(page, country_name)
        finally:
            browser.close()

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
    return jobs
```

- [ ] **Step 5: Run — all pass**

```bash
python -m pytest tests/providers/wellfound/ -v
```

- [ ] **Step 6: Commit**

```bash
git add scripts/providers/wellfound/ tests/providers/wellfound/ tests/fixtures/wellfound/
git commit -m "feat: add wellfound provider (check_auth, scrape_jobs) + tests"
```

---

### Task 11: Sprout provider

**Files:**
- Create: `scripts/providers/sprout/__init__.py`
- Create: `scripts/providers/sprout/check_auth.py`
- Create: `scripts/providers/sprout/scrape_jobs.py`
- Create: `tests/providers/sprout/__init__.py`
- Create: `tests/providers/sprout/test_check_auth.py`
- Create: `tests/providers/sprout/test_scrape_jobs.py`
- Create: `tests/fixtures/sprout/scrape_output.json`

Sprout is different: `collect_sprout()` takes `titles` list (not a single search URL). `scrape_jobs()` uses a hardcoded default title list from the user's profile.

- [ ] **Step 1: Create fixture `tests/fixtures/sprout/scrape_output.json`**

```json
[
  {
    "provider": "sprout",
    "company": "CloudCo",
    "title": "Principal Engineer",
    "url": "https://boards.greenhouse.io/cloudco/jobs/789",
    "location": "Remote",
    "country": "Germany",
    "date": "",
    "salary": ""
  }
]
```

- [ ] **Step 2: Write failing tests**

```python
# tests/providers/sprout/test_check_auth.py
from unittest.mock import MagicMock, patch
import pytest


@patch("scripts.providers.sprout.check_auth.sync_playwright")
def test_already_authenticated(mock_pw):
    page = MagicMock()
    page.url = "https://app.usesprout.com/jobs"
    ctx = MagicMock(); ctx.new_page.return_value = page
    browser = MagicMock(); browser.contexts = [ctx]
    mock_pw.return_value.__enter__.return_value.chromium.connect_over_cdp.return_value = browser
    from scripts.providers.sprout.check_auth import check_auth
    check_auth("http://localhost:9222")


@patch("scripts.providers.sprout.check_auth.sync_playwright")
@patch("scripts.providers.sprout.check_auth.wait_for_auth")
def test_timeout_raises(mock_wait, mock_pw):
    page = MagicMock()
    page.url = "https://app.usesprout.com/login"
    ctx = MagicMock(); ctx.new_page.return_value = page
    browser = MagicMock(); browser.contexts = [ctx]
    mock_pw.return_value.__enter__.return_value.chromium.connect_over_cdp.return_value = browser
    mock_wait.return_value = False
    from scripts.providers.sprout.check_auth import check_auth, AuthError
    with pytest.raises(AuthError):
        check_auth("http://localhost:9222")
```

```python
# tests/providers/sprout/test_scrape_jobs.py
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

FIXTURE = Path(__file__).parent.parent.parent / "fixtures" / "sprout" / "scrape_output.json"


@patch("scripts.providers.sprout.scrape_jobs.collect_sprout")
@patch("scripts.providers.sprout.scrape_jobs.sync_playwright")
def test_returns_shallow_jobs(mock_pw, mock_collect):
    mock_collect.return_value = json.loads(FIXTURE.read_text())
    page = MagicMock()
    ctx = MagicMock(); ctx.new_page.return_value = page
    browser = MagicMock(); browser.contexts = [ctx]
    mock_pw.return_value.__enter__.return_value.chromium.connect_over_cdp.return_value = browser

    from scripts.providers.sprout.scrape_jobs import scrape_jobs
    jobs = scrape_jobs("berlin", "http://localhost:9222")
    assert len(jobs) == 1
    assert jobs[0].company == "CloudCo"
    assert jobs[0].dedup_key == "CloudCo::Principal Engineer"
    assert jobs[0].provider == "sprout"
```

- [ ] **Step 3: Create `scripts/providers/sprout/check_auth.py`**

```python
from __future__ import annotations
import re
from playwright.sync_api import sync_playwright
from scripts.providers._shared.auth_check import wait_for_auth

CHECK_URL = "https://app.usesprout.com/jobs"


class AuthError(Exception):
    pass


def _is_auth_page(url: str) -> bool:
    return bool(re.search(r"/login|/signin|/auth|/register", url, re.I))


def check_auth(cdp_url: str) -> None:
    with sync_playwright() as pw:
        browser = pw.chromium.connect_over_cdp(cdp_url)
        ctx = browser.contexts[0]
        page = ctx.new_page()
        try:
            ok = wait_for_auth(page, "sprout", CHECK_URL, _is_auth_page)
        finally:
            browser.close()
    if not ok:
        raise AuthError("Sprout auth timed out")
```

- [ ] **Step 4: Create `scripts/providers/sprout/scrape_jobs.py`**

```python
from __future__ import annotations
from playwright.sync_api import sync_playwright

from scripts.pipeline.types import ShallowJob
from scripts.providers._shared.job_filter import is_relevant
from scripts.scrape_sprout import LOCATION_PRESETS, SPROUT_BASE, collect_sprout

DEFAULT_TITLES = [
    "Software Engineer", "Backend Engineer", "AI Engineer",
    "Platform Engineer", "Engineering Manager",
]


def scrape_jobs(location: str, cdp_url: str) -> list[ShallowJob]:
    preset_key = location.lower()
    if preset_key not in LOCATION_PRESETS:
        raise ValueError(f"Unknown location: {location!r}")
    country_name = {"berlin": "Germany", "spain": "Spain"}.get(preset_key, location)

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
                titles=DEFAULT_TITLES,
                location=LOCATION_PRESETS[preset_key],
                country=country_name,
            )
        finally:
            browser.close()

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
            country=r.get("country") or country_name,
            dedup_key=f"{r['company']}::{r['title']}",
            posting_date=None,
            salary_raw=r.get("salary") or None,
        )
        if is_relevant({"title": j.title}):
            jobs.append(j)
    return jobs
```

- [ ] **Step 5: Run — all pass**

```bash
python -m pytest tests/providers/sprout/ -v
```

- [ ] **Step 6: Commit**

```bash
git add scripts/providers/sprout/ tests/providers/sprout/ tests/fixtures/sprout/
git commit -m "feat: add sprout provider (check_auth, scrape_jobs) + tests"
```

---

## Chunk 4: Orchestrator + Integration Test

### Task 12: `scraping_pipeline.py`

**Files:**
- Create: `scripts/scraping_pipeline.py`

- [ ] **Step 1: Write failing orchestrator test**

The orchestrator uses **module-level imports** for pipeline functions (patchable via `@patch`) and **dependency injection** for provider functions (passed as `_check_auth`/`_scrape_jobs` keyword args in tests).

```python
# tests/test_scraping_pipeline.py
from unittest.mock import patch, MagicMock
from scripts.pipeline.types import ShallowJob, HermesResult


def _job(company="Acme", title="SWE", url="http://x.com"):
    return ShallowJob(
        provider="greenhouse", title=title, company=company, url=url,
        location="Remote", country="DE",
        dedup_key=f"{company}::{title}",
        posting_date=None, salary_raw=None,
    )


def test_happy_path(db_path, con):
    mock_check_auth = MagicMock()
    mock_scrape = MagicMock(return_value=[_job()])

    # Insert the job that ingest would produce so the DB status check works
    jid = con.execute(
        "INSERT INTO jobs (url, provider, status) VALUES ('http://x.com','greenhouse','new')"
    ).lastrowid
    con.commit()

    with patch("scripts.scraping_pipeline.dedup_jobs", return_value=[_job()]) as mock_dedup, \
         patch("scripts.scraping_pipeline.ingest_jobs", return_value=[jid]) as mock_ingest, \
         patch("scripts.scraping_pipeline.enrich_job") as mock_enrich, \
         patch("scripts.scraping_pipeline.sanity_check_job") as mock_sanity, \
         patch("scripts.scraping_pipeline.send_daily_digest") as mock_notify:

        mock_enrich.return_value = HermesResult(
            success=True, data={"status": "success"}, error=None, raw_output=""
        )
        mock_sanity.return_value = HermesResult(
            success=True, data={"status": "success", "verdict": "pass"},
            error=None, raw_output=""
        )

        from scripts.scraping_pipeline import run
        run(
            provider="greenhouse", location="berlin",
            cdp_url="http://localhost:9222", db_path=db_path,
            _check_auth=mock_check_auth, _scrape_jobs=mock_scrape,
        )

    mock_check_auth.assert_called_once_with("http://localhost:9222")
    mock_scrape.assert_called_once_with("berlin", "http://localhost:9222")
    mock_ingest.assert_called_once()
    mock_enrich.assert_called_once_with(jid, db_path=db_path)
    mock_sanity.assert_called_once_with(jid, db_path=db_path)
    mock_notify.assert_called_once_with(enrich_failures=[], sanity_failures=[])


def test_auth_error_stops_pipeline(db_path):
    from scripts.providers.greenhouse.check_auth import AuthError
    mock_check_auth = MagicMock(side_effect=AuthError("timed out"))
    mock_scrape = MagicMock()

    import pytest
    from scripts.scraping_pipeline import run
    with pytest.raises(AuthError):
        run(
            provider="greenhouse", location="berlin",
            cdp_url="http://localhost:9222", db_path=db_path,
            _check_auth=mock_check_auth, _scrape_jobs=mock_scrape,
        )
    mock_scrape.assert_not_called()


def test_enrich_failure_skips_sanity_for_that_job(db_path, con):
    mock_check_auth = MagicMock()
    mock_scrape = MagicMock(return_value=[_job()])

    # Pre-insert a job with status='enrich_failed' — simulates what enrich_job() would write.
    # The orchestrator queries DB status before deciding whether to call sanity_check_job.
    jid = con.execute(
        "INSERT INTO jobs (url, provider, status) VALUES ('http://x.com','greenhouse','enrich_failed')"
    ).lastrowid
    con.commit()

    with patch("scripts.scraping_pipeline.dedup_jobs", return_value=[_job()]), \
         patch("scripts.scraping_pipeline.ingest_jobs", return_value=[jid]), \
         patch("scripts.scraping_pipeline.enrich_job") as mock_enrich, \
         patch("scripts.scraping_pipeline.sanity_check_job") as mock_sanity, \
         patch("scripts.scraping_pipeline.send_daily_digest") as mock_notify:

        mock_enrich.return_value = HermesResult(
            success=False, data={}, error="timeout", raw_output=""
        )

        from scripts.scraping_pipeline import run
        run(
            provider="greenhouse", location="berlin",
            cdp_url="http://localhost:9222", db_path=db_path,
            _check_auth=mock_check_auth, _scrape_jobs=mock_scrape,
        )

    # sanity check must NOT be called since status == 'enrich_failed', not 'new'
    mock_sanity.assert_not_called()
    failures = mock_notify.call_args[1]["enrich_failures"]
    assert (jid, "timeout") in failures
```

- [ ] **Step 2: Run failing**

```bash
python -m pytest tests/test_scraping_pipeline.py -v
```

- [ ] **Step 3: Create `scripts/scraping_pipeline.py`**

Pipeline functions are module-level imports (patchable by tests). Provider functions are resolved via `importlib` at runtime, but `run()` accepts `_check_auth`/`_scrape_jobs` injection points so tests can bypass the dynamic lookup.

```python
#!/usr/bin/env python3
"""
Scraping pipeline orchestrator.

Usage:
  python3 scripts/scraping_pipeline.py --provider greenhouse --location berlin
  python3 scripts/scraping_pipeline.py --provider jobleads --location spain
  python3 scripts/scraping_pipeline.py --provider wellfound --location berlin
  python3 scripts/scraping_pipeline.py --provider sprout --location berlin

Options:
  --provider <name>   Provider: greenhouse | jobleads | wellfound | sprout
  --location <name>   Location preset: berlin | spain
  --cdp-url <url>     CDP endpoint (default: http://localhost:9222)
  --db <path>         DB path (default: jobs.db in project root)
"""
from __future__ import annotations

import argparse
import importlib
from pathlib import Path

# Module-level imports — patchable in tests via @patch("scripts.scraping_pipeline.<name>")
from scripts.pipeline.dedup import dedup_jobs
from scripts.pipeline.ingest import ingest_jobs
from scripts.pipeline.enrich_job import enrich_job
from scripts.pipeline.sanity_check_job import sanity_check_job
from scripts.pipeline.notify import send_daily_digest
from scripts.db import get_connection

PROJECT_ROOT = Path(__file__).parent.parent
DEFAULT_DB = str(PROJECT_ROOT / "jobs.db")
DEFAULT_CDP = "http://localhost:9222"
PROVIDERS = {"greenhouse", "jobleads", "wellfound", "sprout"}


def run(
    provider: str,
    location: str,
    cdp_url: str = DEFAULT_CDP,
    db_path: str = DEFAULT_DB,
    _check_auth=None,   # injection point for tests
    _scrape_jobs=None,  # injection point for tests
) -> None:
    # Load provider functions (or use injected test doubles)
    auth_mod = importlib.import_module(f"scripts.providers.{provider}.check_auth")
    scrape_mod = importlib.import_module(f"scripts.providers.{provider}.scrape_jobs")
    check_auth_fn = _check_auth or auth_mod.check_auth
    scrape_jobs_fn = _scrape_jobs or scrape_mod.scrape_jobs

    # Phase 1: auth — raises AuthError on failure → hard stop
    check_auth_fn(cdp_url)

    # Phase 2: scrape — exception → Telegram alert + hard stop
    try:
        raw_jobs = scrape_jobs_fn(location, cdp_url)
    except Exception as e:
        from scripts.telegram_notify import pipeline_failure
        pipeline_failure(provider, "scrape", str(e), "")
        raise

    print(f"[pipeline] {provider}: scraped {len(raw_jobs)} jobs", flush=True)

    # Phase 3: dedup
    new_jobs = dedup_jobs(raw_jobs, db_path=db_path)
    print(f"[pipeline] {len(new_jobs)} new after dedup", flush=True)

    # Phase 4: ingest
    job_ids = ingest_jobs(new_jobs, db_path=db_path)
    print(f"[pipeline] ingested {len(job_ids)} jobs", flush=True)

    # Phase 5: enrich
    enrich_failures: list[tuple[int, str]] = []
    for job_id in job_ids:
        result = enrich_job(job_id, db_path=db_path)
        if not result.success:
            enrich_failures.append((job_id, result.error or "unknown"))

    # Phase 6: sanity check — only jobs with status=new (successfully enriched)
    con = get_connection(db_path)
    enriched_ids = []
    for jid in job_ids:
        row = con.execute("SELECT status FROM jobs WHERE id = ?", (jid,)).fetchone()
        if row and row["status"] == "new":
            enriched_ids.append(jid)
    con.close()

    sanity_failures: list[tuple[int, str]] = []
    for job_id in enriched_ids:
        result = sanity_check_job(job_id, db_path=db_path)
        if not result.success:
            sanity_failures.append((job_id, result.error or "unknown"))

    # Phase 7: notify
    send_daily_digest(enrich_failures=enrich_failures, sanity_failures=sanity_failures)
    print(
        f"[pipeline] done. enrich_failures={len(enrich_failures)} "
        f"sanity_failures={len(sanity_failures)}",
        flush=True,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", required=True, choices=PROVIDERS)
    parser.add_argument("--location", required=True)
    parser.add_argument("--cdp-url", default=DEFAULT_CDP)
    parser.add_argument("--db", default=DEFAULT_DB)
    args = parser.parse_args()
    run(
        provider=args.provider,
        location=args.location,
        cdp_url=args.cdp_url,
        db_path=args.db,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run tests — all pass**

```bash
python -m pytest tests/test_scraping_pipeline.py -v
```

- [ ] **Step 5: Run full suite**

```bash
python -m pytest tests/ -v --ignore=tests/e2e
```
Expected: all tests PASS.

- [ ] **Step 6: Commit**

```bash
git add scripts/scraping_pipeline.py tests/test_scraping_pipeline.py
git commit -m "feat: add scraping_pipeline.py orchestrator + integration tests"
```

---

### Task 13: E2E test stub + final wiring

**Files:**
- Create: `tests/e2e/test_greenhouse_live.py`

- [ ] **Step 1: Add pytest marker registration to `tests/conftest.py`**

Append to the existing `tests/conftest.py` created in Task 2:

```python
def pytest_configure(config):
    config.addinivalue_line("markers", "e2e: end-to-end test requiring live Chrome + Hermes")
```

- [ ] **Step 2: Create E2E stub**

```python
# tests/e2e/test_greenhouse_live.py
"""
E2E test — requires real Chrome at localhost:9222 + real Hermes.
Run manually: pytest tests/e2e/ -m e2e -v
"""
import pytest
from scripts.db import create_db


E2E_DB = "/tmp/e2e_test.db"


@pytest.fixture(scope="module", autouse=True)
def setup_e2e_db():
    create_db(E2E_DB)


@pytest.mark.e2e
def test_greenhouse_pipeline_live():
    """Full pipeline against real Greenhouse. Needs Chrome + DB + Hermes."""
    from scripts.scraping_pipeline import run
    run(
        provider="greenhouse",
        location="berlin",
        cdp_url="http://localhost:9222",
        db_path=E2E_DB,
    )
```

- [ ] **Step 3: Verify e2e tests are skipped by default**

```bash
python -m pytest tests/ --ignore=tests/e2e -v
```
Expected: all PASS, e2e directory not executed.

- [ ] **Step 4: Final smoke run of entire suite**

```bash
python -m pytest tests/ --ignore=tests/e2e -q
```
Expected: all green, no marker warnings.

- [ ] **Step 5: Final commit**

```bash
git add tests/e2e/ tests/conftest.py
git commit -m "feat: add e2e test stub, pytest marker registration"
```
