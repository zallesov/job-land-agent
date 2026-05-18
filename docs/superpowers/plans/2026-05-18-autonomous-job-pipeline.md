# Autonomous Job Pipeline Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an autonomous local job pipeline: SQLite canonical store → provider ingestion → Next.js dashboard → research worker → Hermes daily scrape+ingest cron → Telegram notifications.

**Architecture:** SQLite at `jobs.db` is the single source of truth. Python scripts own all DB writes (ingestion, tagging, research). Next.js App Router reads SQLite on the server via `better-sqlite3` and triggers research by spawning `scripts/research_job.py` as a background process. Hermes cron owns daily scraping via existing skills + runs ingestion/tagging scripts + sends Telegram digest via `hermes send`.

**Tech Stack:** Python 3.14 + sqlite3 stdlib, Next.js 14 App Router + better-sqlite3 + Tailwind CSS, Anthropic SDK (python) for research, `hermes send` for Telegram delivery, Hermes cron for daily scheduling.

---

## File Map

```
/Users/zall/interviews/
├── jobs.db                                     ← SQLite canonical store (auto-created)
├── scripts/
│   ├── db.py                                   ← Shared DB: create_db(), repo functions
│   ├── ingest_provider_outputs.py              ← CLI: normalize + upsert jobs/companies
│   ├── tag_new_jobs.py                         ← CLI: cheap keyword tags on new jobs
│   ├── research_job.py                         ← CLI: research one job via Claude API
│   └── telegram_notify.py                      ← Helpers: format + send via hermes send
├── dashboard/                                  ← Next.js App Router app
│   ├── package.json
│   ├── next.config.ts
│   ├── tailwind.config.ts
│   ├── lib/
│   │   └── db.ts                               ← better-sqlite3 server-only access
│   └── app/
│       ├── layout.tsx
│       ├── page.tsx                            ← Main dashboard (server component)
│       ├── actions.ts                          ← Server actions: edit fields, add URL
│       ├── api/
│       │   └── commands/route.ts               ← POST /api/commands → trigger research
│       └── components/
│           ├── JobList.tsx                     ← Client: selectable job rows
│           ├── JobDetail.tsx                   ← Client: detail pane
│           ├── FilterBar.tsx                   ← Client: filter/sort controls
│           └── CommandButton.tsx               ← Client: research trigger + status
└── .codex/skills/daily-pipeline/
    └── SKILL.md                                ← Hermes daily pipeline skill
```

---

## Chunk 1: SQLite Foundation

### Task 1: Create DB module with schema

**Files:**
- Create: `scripts/db.py`
- Create: `scripts/test_db.py`

- [ ] **Step 1: Write failing tests**

Create `scripts/test_db.py`:

```python
import os
import tempfile
import pytest
from db import create_db, get_connection

def make_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    create_db(path)
    return path

def test_creates_all_tables():
    path = make_db()
    con = get_connection(path)
    tables = {r[0] for r in con.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()}
    expected = {"jobs", "companies", "company_research", "job_assessments",
                "applications", "agent_commands", "pipeline_runs", "events"}
    assert expected.issubset(tables)
    con.close()
    os.unlink(path)

def test_job_url_unique():
    path = make_db()
    con = get_connection(path)
    con.execute(
        "INSERT INTO jobs (url, provider, status) VALUES (?, ?, ?)",
        ("https://example.com/job/1", "greenhouse", "new")
    )
    con.commit()
    with pytest.raises(Exception):
        con.execute(
            "INSERT INTO jobs (url, provider, status) VALUES (?, ?, ?)",
            ("https://example.com/job/1", "greenhouse", "new")
        )
        con.commit()
    con.close()
    os.unlink(path)

def test_foreign_keys_enabled():
    path = make_db()
    con = get_connection(path)
    result = con.execute("PRAGMA foreign_keys").fetchone()
    assert result[0] == 1
    con.close()
    os.unlink(path)

def test_indexes_exist():
    path = make_db()
    con = get_connection(path)
    indexes = {r[1] for r in con.execute(
        "SELECT * FROM sqlite_master WHERE type='index'"
    ).fetchall()}
    for expected_idx in ["idx_jobs_url", "idx_jobs_status", "idx_jobs_provider",
                         "idx_companies_domain", "idx_agent_commands_status"]:
        assert expected_idx in indexes, f"Missing index: {expected_idx}"
    con.close()
    os.unlink(path)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/zall/interviews/scripts && python3 -m pytest test_db.py -v 2>&1 | head -30
```
Expected: `ModuleNotFoundError: No module named 'db'`

- [ ] **Step 3: Write `scripts/db.py`**

```python
import sqlite3
from pathlib import Path


def get_connection(db_path: str) -> sqlite3.Connection:
    con = sqlite3.connect(db_path)
    con.execute("PRAGMA foreign_keys = ON")
    con.execute("PRAGMA journal_mode = WAL")
    con.row_factory = sqlite3.Row
    return con


def create_db(db_path: str) -> None:
    con = get_connection(db_path)
    cur = con.cursor()

    cur.executescript("""
    CREATE TABLE IF NOT EXISTS companies (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        display_name TEXT NOT NULL,
        normalized_name TEXT NOT NULL,
        website_url TEXT,
        domain TEXT,
        linkedin_url TEXT,
        glassdoor_url TEXT,
        crunchbase_url TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS jobs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        url TEXT NOT NULL UNIQUE,
        provider TEXT NOT NULL,
        provider_job_id TEXT,
        company_id INTEGER REFERENCES companies(id),
        posted_company_name TEXT,
        actual_hiring_company_id INTEGER REFERENCES companies(id),
        title TEXT,
        description TEXT,
        apply_url TEXT,
        location TEXT,
        country TEXT,
        remote_scope TEXT,
        date_posted TEXT,
        first_seen TEXT NOT NULL DEFAULT (datetime('now')),
        last_seen TEXT NOT NULL DEFAULT (datetime('now')),
        status TEXT NOT NULL DEFAULT 'new',
        comment TEXT,
        current_interview_status TEXT,
        source_payload_json TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS company_research (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        company_id INTEGER NOT NULL REFERENCES companies(id),
        researched_at TEXT,
        research_status TEXT NOT NULL DEFAULT 'pending',
        legitimacy_check TEXT,
        hiring_entity_type TEXT,
        founded_year INTEGER,
        hq_location TEXT,
        employee_count TEXT,
        headcount_trend TEXT,
        funding_summary TEXT,
        funding_stage TEXT,
        risk_news TEXT,
        glassdoor_summary TEXT,
        trustworthiness_score INTEGER,
        research_notes TEXT,
        source_urls_json TEXT,
        raw_research_json TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS job_assessments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id INTEGER NOT NULL UNIQUE REFERENCES jobs(id),
        assessed_at TEXT,
        assessment_status TEXT NOT NULL DEFAULT 'pending',
        relevance_score INTEGER,
        apply_verdict TEXT,
        one_line_summary TEXT,
        red_flag_scan TEXT,
        seniority_fit TEXT,
        tech_stack_fit TEXT,
        ic_or_management TEXT,
        salary_assessment TEXT,
        remote_eligibility TEXT,
        visa_contract_structure TEXT,
        ai_native_assessment TEXT,
        assessment_notes TEXT,
        source_urls_json TEXT,
        raw_assessment_json TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS applications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id INTEGER NOT NULL REFERENCES jobs(id),
        status TEXT NOT NULL DEFAULT 'draft_requested',
        tailored_cv_path TEXT,
        cover_letter_path TEXT,
        application_notes_path TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        submitted_at TEXT,
        updated_at TEXT NOT NULL DEFAULT (datetime('now')),
        error TEXT
    );

    CREATE TABLE IF NOT EXISTS agent_commands (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        command_type TEXT NOT NULL,
        payload_json TEXT,
        status TEXT NOT NULL DEFAULT 'pending',
        created_by TEXT NOT NULL DEFAULT 'system',
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        started_at TEXT,
        finished_at TEXT,
        result_json TEXT,
        error TEXT
    );

    CREATE TABLE IF NOT EXISTS pipeline_runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_type TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'running',
        started_at TEXT NOT NULL DEFAULT (datetime('now')),
        finished_at TEXT,
        summary_json TEXT,
        error TEXT
    );

    CREATE TABLE IF NOT EXISTS events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        entity_type TEXT NOT NULL,
        entity_id INTEGER,
        event_type TEXT NOT NULL,
        actor TEXT NOT NULL DEFAULT 'system',
        event_json TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    );

    CREATE UNIQUE INDEX IF NOT EXISTS idx_jobs_url ON jobs(url);
    CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
    CREATE INDEX IF NOT EXISTS idx_jobs_provider ON jobs(provider);
    CREATE INDEX IF NOT EXISTS idx_jobs_country ON jobs(country);
    CREATE INDEX IF NOT EXISTS idx_jobs_company_id ON jobs(company_id);
    CREATE INDEX IF NOT EXISTS idx_companies_domain ON companies(domain);
    CREATE INDEX IF NOT EXISTS idx_companies_normalized_name ON companies(normalized_name);
    CREATE INDEX IF NOT EXISTS idx_agent_commands_status ON agent_commands(status);
    CREATE INDEX IF NOT EXISTS idx_pipeline_runs_started_at ON pipeline_runs(started_at);
    """)

    con.commit()
    con.close()


def _normalize_name(name: str) -> str:
    import re
    return re.sub(r"[^a-z0-9]", "", name.lower().strip())


def upsert_company(con: sqlite3.Connection, display_name: str, domain: str | None = None) -> int:
    normalized = _normalize_name(display_name)
    if domain:
        row = con.execute("SELECT id FROM companies WHERE domain = ?", (domain,)).fetchone()
    else:
        row = con.execute(
            "SELECT id FROM companies WHERE normalized_name = ? AND domain IS NULL",
            (normalized,)
        ).fetchone()
    if row:
        return row["id"]
    cur = con.execute(
        "INSERT INTO companies (display_name, normalized_name, domain) VALUES (?, ?, ?)",
        (display_name, normalized, domain)
    )
    return cur.lastrowid


def get_job_by_url(con: sqlite3.Connection, url: str) -> sqlite3.Row | None:
    return con.execute("SELECT * FROM jobs WHERE url = ?", (url,)).fetchone()


def insert_job(con: sqlite3.Connection, **fields) -> int:
    cols = ", ".join(fields.keys())
    placeholders = ", ".join("?" * len(fields))
    cur = con.execute(
        f"INSERT INTO jobs ({cols}) VALUES ({placeholders})",
        list(fields.values())
    )
    return cur.lastrowid


def update_job_machine_fields(con: sqlite3.Connection, job_id: int, **fields) -> None:
    PROTECTED = {"status", "comment", "current_interview_status"}
    safe = {k: v for k, v in fields.items() if k not in PROTECTED}
    if not safe:
        return
    set_parts = [f"{k} = ?" for k in safe]
    set_parts.append("updated_at = datetime('now')")
    params = list(safe.values()) + [job_id]
    con.execute(
        f"UPDATE jobs SET {', '.join(set_parts)} WHERE id = ?",
        params
    )


def log_event(con: sqlite3.Connection, entity_type: str, entity_id: int,
              event_type: str, actor: str = "system", event_json: str | None = None) -> None:
    con.execute(
        "INSERT INTO events (entity_type, entity_id, event_type, actor, event_json) "
        "VALUES (?, ?, ?, ?, ?)",
        (entity_type, entity_id, event_type, actor, event_json)
    )


def create_pipeline_run(con: sqlite3.Connection, run_type: str) -> int:
    cur = con.execute(
        "INSERT INTO pipeline_runs (run_type, status) VALUES (?, 'running')",
        (run_type,)
    )
    return cur.lastrowid


def finish_pipeline_run(con: sqlite3.Connection, run_id: int, status: str,
                        summary_json: str | None = None, error: str | None = None) -> None:
    con.execute(
        "UPDATE pipeline_runs SET status = ?, finished_at = datetime('now'), "
        "summary_json = ?, error = ? WHERE id = ?",
        (status, summary_json, error, run_id)
    )
```

- [ ] **Step 4: Run tests**

```bash
cd /Users/zall/interviews/scripts && python3 -m pytest test_db.py -v
```
Expected: 4 tests PASS

- [ ] **Step 5: Smoke-create the real DB**

```bash
cd /Users/zall/interviews && python3 -c "
import sys; sys.path.insert(0, 'scripts')
from db import create_db
create_db('jobs.db')
print('DB created')
"
```
Expected: `DB created`

---

## Chunk 2: Ingestion Script

### Task 2: Ingestion CLI

**Files:**
- Create: `scripts/ingest_provider_outputs.py`
- Create: `scripts/test_ingestion.py`

- [ ] **Step 1: Inspect existing run formats**

Both providers use this shape (with minor differences):
- `provider`, `company`, `title`, `url`, `description`, `applyUrl`, `location`, `country`, `postingDate` (greenhouse also has `searchQuery`, jobleads has `postedRelative`)
- Missing from spec shape: `providerJobId`, `remoteScope` (derive from location/description), `datePosted` maps from `postingDate`

- [ ] **Step 2: Write failing tests**

Create `scripts/test_ingestion.py`:

```python
import json
import os
import tempfile
import pytest
import sys
sys.path.insert(0, os.path.dirname(__file__))

from db import create_db, get_connection
from ingest_provider_outputs import normalize_job, ingest_run_file, ingest_all_latest

SAMPLE_JOB = {
    "provider": "greenhouse",
    "company": "Acme Corp",
    "title": "Senior Engineer",
    "url": "https://job-boards.greenhouse.io/acme/jobs/123",
    "description": "Build stuff. Remote friendly.",
    "applyUrl": "https://job-boards.greenhouse.io/acme/jobs/123",
    "location": "Remote",
    "country": "Germany",
    "postingDate": "2026-05-18",
    "searchLabel": "Software Engineer - Berlin Remote",
    "searchQuery": "Software Engineer"
}

def make_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    create_db(path)
    return path

def make_run_file(jobs: list) -> str:
    fd, path = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    with open(path, "w") as f:
        json.dump(jobs, f)
    return path

def test_normalize_job_maps_fields():
    n = normalize_job(SAMPLE_JOB)
    assert n["url"] == SAMPLE_JOB["url"]
    assert n["provider"] == "greenhouse"
    assert n["posted_company_name"] == "Acme Corp"
    assert n["date_posted"] == "2026-05-18"
    assert "source_payload" in n

def test_ingest_inserts_job_and_company():
    db_path = make_db()
    run_path = make_run_file([SAMPLE_JOB])
    result = ingest_run_file(db_path, run_path)
    assert result["inserted"] == 1
    assert result["updated"] == 0
    assert result["failed"] == 0
    con = get_connection(db_path)
    job = con.execute("SELECT * FROM jobs WHERE url = ?", (SAMPLE_JOB["url"],)).fetchone()
    assert job is not None
    assert job["title"] == "Senior Engineer"
    company = con.execute("SELECT * FROM companies WHERE id = ?", (job["company_id"],)).fetchone()
    assert company is not None
    assert company["display_name"] == "Acme Corp"
    con.close()
    os.unlink(db_path)
    os.unlink(run_path)

def test_ingest_dedupes_by_url():
    db_path = make_db()
    run_path = make_run_file([SAMPLE_JOB])
    ingest_run_file(db_path, run_path)
    result = ingest_run_file(db_path, run_path)
    assert result["inserted"] == 0
    assert result["updated"] == 1
    con = get_connection(db_path)
    count = con.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
    assert count == 1
    con.close()
    os.unlink(db_path)
    os.unlink(run_path)

def test_ingest_preserves_manual_fields():
    db_path = make_db()
    run_path = make_run_file([SAMPLE_JOB])
    ingest_run_file(db_path, run_path)
    con = get_connection(db_path)
    con.execute(
        "UPDATE jobs SET status = 'interesting', comment = 'looks good' WHERE url = ?",
        (SAMPLE_JOB["url"],)
    )
    con.commit()
    con.close()
    ingest_run_file(db_path, run_path)
    con = get_connection(db_path)
    job = con.execute("SELECT * FROM jobs WHERE url = ?", (SAMPLE_JOB["url"],)).fetchone()
    assert job["status"] == "interesting"
    assert job["comment"] == "looks good"
    con.close()
    os.unlink(db_path)
    os.unlink(run_path)

def test_ingest_same_company_domain_one_record():
    db_path = make_db()
    job2 = {**SAMPLE_JOB, "url": "https://job-boards.greenhouse.io/acme/jobs/456", "title": "PM"}
    run_path = make_run_file([SAMPLE_JOB, job2])
    ingest_run_file(db_path, run_path)
    con = get_connection(db_path)
    count = con.execute("SELECT COUNT(*) FROM companies").fetchone()[0]
    assert count == 1
    con.close()
    os.unlink(db_path)
    os.unlink(run_path)

def test_ingest_malformed_json_returns_error():
    db_path = make_db()
    fd, run_path = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    with open(run_path, "w") as f:
        f.write("not valid json {{{")
    result = ingest_run_file(db_path, run_path)
    assert result["failed"] > 0 or result.get("error")
    con = get_connection(db_path)
    count = con.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
    assert count == 0
    con.close()
    os.unlink(db_path)
    os.unlink(run_path)

def test_pipeline_run_record_created():
    db_path = make_db()
    run_path = make_run_file([SAMPLE_JOB])
    ingest_run_file(db_path, run_path)
    con = get_connection(db_path)
    run = con.execute("SELECT * FROM pipeline_runs ORDER BY id DESC LIMIT 1").fetchone()
    assert run is not None
    assert run["status"] in ("succeeded", "partial", "failed")
    con.close()
    os.unlink(db_path)
    os.unlink(run_path)
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
cd /Users/zall/interviews/scripts && python3 -m pytest test_ingestion.py -v 2>&1 | head -20
```
Expected: `ModuleNotFoundError: No module named 'ingest_provider_outputs'`

- [ ] **Step 4: Write `scripts/ingest_provider_outputs.py`**

```python
#!/usr/bin/env python3
"""
Ingest normalized provider JSON arrays into SQLite.

Usage:
  python3 ingest_provider_outputs.py --db jobs.db --run-file outputs/greenhouse/runs/greenhouse_jobs_live_2026-05-18.json
  python3 ingest_provider_outputs.py --db jobs.db --all-latest
"""
import argparse
import json
import os
import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from db import (
    create_db, get_connection, upsert_company, get_job_by_url,
    insert_job, update_job_machine_fields, log_event,
    create_pipeline_run, finish_pipeline_run
)

PROVIDERS_DIR = Path(__file__).parent.parent / "outputs"


def _extract_domain(url: str | None) -> str | None:
    if not url:
        return None
    m = re.search(r"https?://(?:www\.)?([^/]+)", url)
    return m.group(1).lower() if m else None


def _detect_remote_scope(location: str, description: str) -> str:
    text = f"{location} {description}".lower()
    if "fully remote" in text or "100% remote" in text:
        return "remote"
    if "remote" in text and "hybrid" in text:
        return "hybrid"
    if "remote" in text:
        return "remote"
    if "on-site" in text or "onsite" in text or "in-office" in text:
        return "onsite"
    return "unknown"


def normalize_job(raw: dict) -> dict:
    extra = {k: raw[k] for k in raw if k not in {
        "provider", "company", "title", "url", "description",
        "applyUrl", "location", "country", "postingDate", "datePosted"
    }}
    return {
        "provider": raw.get("provider", "unknown"),
        "url": raw["url"].strip(),
        "apply_url": raw.get("applyUrl") or raw.get("apply_url"),
        "posted_company_name": raw.get("company", ""),
        "title": raw.get("title", ""),
        "description": raw.get("description", ""),
        "location": raw.get("location", ""),
        "country": raw.get("country", ""),
        "remote_scope": _detect_remote_scope(
            raw.get("location", ""), raw.get("description", "")
        ),
        "date_posted": raw.get("postingDate") or raw.get("datePosted") or "",
        "source_payload": extra,
    }


def ingest_run_file(db_path: str, run_file: str) -> dict:
    result = {"inserted": 0, "updated": 0, "skipped": 0, "failed": 0, "error": None}
    con = get_connection(db_path)
    run_id = create_pipeline_run(con, f"ingest:{Path(run_file).name}")
    con.commit()

    try:
        with open(run_file) as f:
            raw_jobs = json.load(f)
    except Exception as e:
        result["failed"] = 1
        result["error"] = str(e)
        finish_pipeline_run(con, run_id, "failed", error=str(e),
                            summary_json=json.dumps(result))
        con.commit()
        con.close()
        return result

    if not isinstance(raw_jobs, list):
        result["failed"] = 1
        result["error"] = "Top-level JSON must be an array"
        finish_pipeline_run(con, run_id, "failed", error=result["error"],
                            summary_json=json.dumps(result))
        con.commit()
        con.close()
        return result

    for raw in raw_jobs:
        try:
            n = normalize_job(raw)
            if not n["url"]:
                result["skipped"] += 1
                continue
            domain = _extract_domain(
                raw.get("company_website") or raw.get("applyUrl")
            )
            company_id = upsert_company(con, n["posted_company_name"], domain)
            existing = get_job_by_url(con, n["url"])
            if existing is None:
                job_id = insert_job(
                    con,
                    url=n["url"],
                    provider=n["provider"],
                    company_id=company_id,
                    posted_company_name=n["posted_company_name"],
                    title=n["title"],
                    description=n["description"],
                    apply_url=n["apply_url"],
                    location=n["location"],
                    country=n["country"],
                    remote_scope=n["remote_scope"],
                    date_posted=n["date_posted"],
                    source_payload_json=json.dumps(n["source_payload"]),
                    status="new",
                )
                log_event(con, "job", job_id, "job_inserted", "ingest",
                          json.dumps({"provider": n["provider"], "url": n["url"]}))
                result["inserted"] += 1
            else:
                job_id = existing["id"]
                # Merge new source_payload into existing, preserving light_* tags
                existing_payload: dict = {}
                if existing["source_payload_json"]:
                    try:
                        existing_payload = json.loads(existing["source_payload_json"])
                    except Exception:
                        pass
                existing_payload.update(n["source_payload"])
                merged_payload = json.dumps(existing_payload)

                set_parts = [
                    "last_seen = datetime('now')",
                    "source_payload_json = ?",
                    "updated_at = datetime('now')",
                ]
                params: list = [merged_payload]
                if not existing["apply_url"] and n["apply_url"]:
                    set_parts.append("apply_url = ?")
                    params.append(n["apply_url"])
                if not existing["description"] and n["description"]:
                    set_parts.append("description = ?")
                    params.append(n["description"])
                params.append(job_id)
                con.execute(
                    f"UPDATE jobs SET {', '.join(set_parts)} WHERE id = ?",
                    params
                )
                log_event(con, "job", job_id, "job_seen_again", "ingest",
                          json.dumps({"provider": n["provider"]}))
                result["updated"] += 1
        except Exception as e:
            result["failed"] += 1
            continue

    status = "succeeded" if result["failed"] == 0 else (
        "partial" if result["inserted"] + result["updated"] > 0 else "failed"
    )
    finish_pipeline_run(con, run_id, status, summary_json=json.dumps(result))
    con.commit()
    con.close()
    return result


def find_latest_run_files() -> list[Path]:
    files = []
    if not PROVIDERS_DIR.exists():
        return files
    for provider_dir in PROVIDERS_DIR.iterdir():
        runs_dir = provider_dir / "runs"
        if not runs_dir.is_dir():
            continue
        json_files = sorted(runs_dir.glob("*_jobs_live_*.json"), reverse=True)
        if json_files:
            files.append(json_files[0])
    return files


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", required=True)
    parser.add_argument("--run-file")
    parser.add_argument("--all-latest", action="store_true")
    args = parser.parse_args()

    if not Path(args.db).exists():
        create_db(args.db)

    if args.run_file:
        result = ingest_run_file(args.db, args.run_file)
        print(json.dumps(result, indent=2))
    elif args.all_latest:
        files = find_latest_run_files()
        if not files:
            print("No run files found")
            sys.exit(0)
        totals = {"inserted": 0, "updated": 0, "skipped": 0, "failed": 0}
        for f in files:
            r = ingest_run_file(args.db, str(f))
            print(f"{f.name}: inserted={r['inserted']} updated={r['updated']} failed={r['failed']}")
            for k in totals:
                totals[k] += r[k]
        print(f"Total: {json.dumps(totals)}")
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Run tests**

```bash
cd /Users/zall/interviews/scripts && python3 -m pytest test_ingestion.py -v
```
Expected: 7 tests PASS (or near - the update test may need adjustment for the SQL building logic)

- [ ] **Step 6: Smoke-ingest existing run files**

```bash
cd /Users/zall/interviews && python3 scripts/ingest_provider_outputs.py \
  --db jobs.db --all-latest
```
Expected: inserted=32 updated=0 failed=0 (from greenhouse) + similar for jobleads

---

## Chunk 3: Next.js Dashboard Scaffold

### Task 3: Initialize Next.js app

**Files:**
- Create: `dashboard/package.json`
- Create: `dashboard/next.config.ts`
- Create: `dashboard/tailwind.config.ts`
- Create: `dashboard/lib/db.ts`

- [ ] **Step 1: Scaffold Next.js app**

```bash
cd /Users/zall/interviews && npx create-next-app@14 dashboard \
  --typescript --tailwind --app --src-dir no --import-alias "@/*" --no-git
```

When prompted: accept all defaults.

- [ ] **Step 2: Install better-sqlite3**

```bash
cd /Users/zall/interviews/dashboard && npm install better-sqlite3 && npm install --save-dev @types/better-sqlite3
```

- [ ] **Step 3: Create `dashboard/lib/db.ts`**

```typescript
// Server-only SQLite access. Never import this in client components.
import Database from "better-sqlite3";
import path from "path";

const DB_PATH = path.resolve(process.cwd(), "../jobs.db");

let _db: Database.Database | null = null;

export function getDb(): Database.Database {
  if (!_db) {
    _db = new Database(DB_PATH, { readonly: false });
    _db.pragma("foreign_keys = ON");
    _db.pragma("journal_mode = WAL");
  }
  return _db;
}

export type Job = {
  id: number;
  url: string;
  provider: string;
  posted_company_name: string | null;
  title: string | null;
  location: string | null;
  country: string | null;
  remote_scope: string | null;
  status: string;
  comment: string | null;
  current_interview_status: string | null;
  first_seen: string;
  last_seen: string;
  company_id: number | null;
  apply_url: string | null;
  description: string | null;
  source_payload_json: string | null;
};

export type JobAssessment = {
  id: number;
  job_id: number;
  assessment_status: string;
  relevance_score: number | null;
  apply_verdict: string | null;
  one_line_summary: string | null;
  red_flag_scan: string | null;
  seniority_fit: string | null;
  tech_stack_fit: string | null;
  salary_assessment: string | null;
  remote_eligibility: string | null;
  assessed_at: string | null;
};

export type CompanyResearch = {
  id: number;
  company_id: number;
  trustworthiness_score: number | null;
  research_status: string;
  legitimacy_check: string | null;
  hiring_entity_type: string | null;
  glassdoor_summary: string | null;
  funding_summary: string | null;
  research_notes: string | null;
  researched_at: string | null;
};

export type AgentCommand = {
  id: number;
  command_type: string;
  payload_json: string | null;
  status: string;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  result_json: string | null;
  error: string | null;
};
```

- [ ] **Step 4: Verify Next.js compiles**

```bash
cd /Users/zall/interviews/dashboard && npm run build 2>&1 | tail -10
```
Expected: Build succeeds.

---

## Chunk 4: Dashboard UI

### Task 4: Main page + server queries

**Files:**
- Create/Modify: `dashboard/app/page.tsx`
- Create: `dashboard/app/actions.ts`
- Create: `dashboard/app/components/JobList.tsx`
- Create: `dashboard/app/components/JobDetail.tsx`
- Create: `dashboard/app/components/FilterBar.tsx`
- Create: `dashboard/app/components/CommandButton.tsx`

- [ ] **Step 1: Create server query helpers in `dashboard/lib/db.ts`** (append to existing file)

```typescript
// append to dashboard/lib/db.ts

export type JobFilters = {
  status?: string;
  provider?: string;
  country?: string;
  remote_scope?: string;
  unresearched?: boolean;
  new_only?: boolean;
};

export function listJobs(filters: JobFilters = {}): (Job & {
  relevance_score: number | null;
  apply_verdict: string | null;
  trustworthiness_score: number | null;
})[] {
  const db = getDb();
  const conditions: string[] = [];
  const params: unknown[] = [];

  if (filters.status) { conditions.push("j.status = ?"); params.push(filters.status); }
  if (filters.provider) { conditions.push("j.provider = ?"); params.push(filters.provider); }
  if (filters.country) { conditions.push("j.country = ?"); params.push(filters.country); }
  if (filters.remote_scope) { conditions.push("j.remote_scope = ?"); params.push(filters.remote_scope); }
  if (filters.unresearched) { conditions.push("ja.id IS NULL"); }
  if (filters.new_only) { conditions.push("j.status = 'new'"); }

  const where = conditions.length ? `WHERE ${conditions.join(" AND ")}` : "";
  const sql = `
    SELECT j.*,
           ja.relevance_score, ja.apply_verdict,
           cr.trustworthiness_score
    FROM jobs j
    LEFT JOIN job_assessments ja ON ja.job_id = j.id
    LEFT JOIN company_research cr ON cr.company_id = j.company_id
    ${where}
    ORDER BY
      CASE j.status WHEN 'new' THEN 0 ELSE 1 END,
      COALESCE(ja.relevance_score, 0) DESC,
      COALESCE(cr.trustworthiness_score, 0) DESC,
      j.first_seen DESC
    LIMIT 500
  `;
  return db.prepare(sql).all(...params) as any;
}

export function getJobDetail(id: number): {
  job: Job;
  assessment: JobAssessment | null;
  research: CompanyResearch | null;
  commands: AgentCommand[];
} | null {
  const db = getDb();
  const job = db.prepare("SELECT * FROM jobs WHERE id = ?").get(id) as Job | undefined;
  if (!job) return null;
  const assessment = db.prepare("SELECT * FROM job_assessments WHERE job_id = ?").get(id) as JobAssessment | null;
  const research = job.company_id
    ? db.prepare("SELECT * FROM company_research WHERE company_id = ?").get(job.company_id) as CompanyResearch | null
    : null;
  const commands = db.prepare(
    "SELECT * FROM agent_commands WHERE json_extract(payload_json, '$.job_id') = ? ORDER BY created_at DESC LIMIT 10"
  ).all(id) as AgentCommand[];
  return { job, assessment, research, commands };
}

export function addManualJob(url: string): { id: number; created: boolean } {
  const db = getDb();
  const existing = db.prepare("SELECT id FROM jobs WHERE url = ?").get(url) as { id: number } | undefined;
  if (existing) return { id: existing.id, created: false };
  const result = db.prepare(
    "INSERT INTO jobs (url, provider, status) VALUES (?, 'manual', 'new')"
  ).run(url);
  const id = result.lastInsertRowid as number;
  db.prepare(
    "INSERT INTO events (entity_type, entity_id, event_type, actor) VALUES ('job', ?, 'job_inserted', 'ui')"
  ).run(id);
  return { id, created: true };
}

export function updateJobWorkflowFields(
  id: number,
  fields: { status?: string; comment?: string; current_interview_status?: string }
): void {
  const db = getDb();
  const updates: string[] = [];
  const params: unknown[] = [];
  if (fields.status !== undefined) { updates.push("status = ?"); params.push(fields.status); }
  if (fields.comment !== undefined) { updates.push("comment = ?"); params.push(fields.comment); }
  if (fields.current_interview_status !== undefined) {
    updates.push("current_interview_status = ?"); params.push(fields.current_interview_status);
  }
  if (!updates.length) return;
  updates.push("updated_at = datetime('now')");
  params.push(id);
  db.prepare(`UPDATE jobs SET ${updates.join(", ")} WHERE id = ?`).run(...params);
}

export function createResearchCommand(jobId: number): { commandId: number; existing: boolean } {
  const db = getDb();
  const existing = db.prepare(
    "SELECT id FROM agent_commands WHERE command_type = 'research_job' AND status IN ('pending','running') AND json_extract(payload_json,'$.job_id') = ?"
  ).get(jobId) as { id: number } | undefined;
  if (existing) return { commandId: existing.id, existing: true };
  const result = db.prepare(
    "INSERT INTO agent_commands (command_type, payload_json, status, created_by) VALUES ('research_job', ?, 'pending', 'ui')"
  ).run(JSON.stringify({ job_id: jobId }));
  return { commandId: result.lastInsertRowid as number, existing: false };
}
```

- [ ] **Step 2: Create `dashboard/app/actions.ts`**

```typescript
"use server";
import { addManualJob, updateJobWorkflowFields } from "@/lib/db";
import { revalidatePath } from "next/cache";

export async function addManualJobAction(formData: FormData) {
  const url = (formData.get("url") as string)?.trim();
  if (!url || !url.startsWith("http")) throw new Error("Invalid URL");
  const result = addManualJob(url);
  revalidatePath("/");
  return result;
}

export async function updateJobAction(
  jobId: number,
  fields: { status?: string; comment?: string; current_interview_status?: string }
) {
  updateJobWorkflowFields(jobId, fields);
  revalidatePath("/");
}
```

- [ ] **Step 3: Create `dashboard/app/page.tsx`** (server component)

```tsx
import { listJobs, type JobFilters } from "@/lib/db";
import { JobListClient } from "./components/JobList";
import { addManualJobAction } from "./actions";

export default function DashboardPage({
  searchParams,
}: {
  searchParams: { [key: string]: string | undefined };
}) {
  const filters: JobFilters = {
    status: searchParams.status,
    provider: searchParams.provider,
    country: searchParams.country,
    remote_scope: searchParams.remote_scope,
    unresearched: searchParams.unresearched === "1",
    new_only: searchParams.new_only === "1",
  };
  const jobs = listJobs(filters);

  return (
    <div className="flex flex-col h-screen bg-gray-950 text-gray-100">
      <header className="flex items-center justify-between px-4 py-2 border-b border-gray-800">
        <h1 className="text-lg font-bold tracking-tight">Job Pipeline</h1>
        <span className="text-sm text-gray-400">{jobs.length} jobs</span>
      </header>

      <div className="flex flex-1 overflow-hidden">
        <JobListClient jobs={jobs} addJobAction={addManualJobAction} />
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Create `dashboard/app/components/JobList.tsx`** (client component)

```tsx
"use client";
import { useState } from "react";
import { JobDetail } from "./JobDetail";

const STATUS_COLORS: Record<string, string> = {
  new: "bg-blue-900 text-blue-200",
  interesting: "bg-green-900 text-green-200",
  not_interested: "bg-gray-700 text-gray-400",
  researching: "bg-yellow-900 text-yellow-200",
  researched: "bg-purple-900 text-purple-200",
  applied: "bg-indigo-900 text-indigo-200",
  interviewing: "bg-teal-900 text-teal-200",
  rejected: "bg-red-900 text-red-300",
  archived: "bg-gray-800 text-gray-500",
};

export function JobListClient({ jobs, addJobAction }: {
  jobs: any[];
  addJobAction: (fd: FormData) => Promise<any>;
}) {
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [addUrl, setAddUrl] = useState("");
  const [adding, setAdding] = useState(false);

  const selected = jobs.find((j) => j.id === selectedId) ?? null;

  async function handleAdd(e: React.FormEvent) {
    e.preventDefault();
    setAdding(true);
    const fd = new FormData();
    fd.set("url", addUrl);
    await addJobAction(fd);
    setAddUrl("");
    setAdding(false);
  }

  return (
    <>
      {/* Left pane: filter + list */}
      <div className="w-[480px] flex flex-col border-r border-gray-800 overflow-hidden">
        <form onSubmit={handleAdd} className="flex gap-2 px-3 py-2 border-b border-gray-800">
          <input
            className="flex-1 bg-gray-900 border border-gray-700 rounded px-2 py-1 text-sm"
            placeholder="Add job URL..."
            value={addUrl}
            onChange={(e) => setAddUrl(e.target.value)}
          />
          <button
            type="submit"
            disabled={adding}
            className="bg-blue-700 hover:bg-blue-600 text-white rounded px-3 py-1 text-sm"
          >
            Add
          </button>
        </form>
        <div className="overflow-y-auto flex-1">
          {jobs.map((job) => (
            <button
              key={job.id}
              onClick={() => setSelectedId(job.id)}
              className={`w-full text-left px-3 py-2 border-b border-gray-800 hover:bg-gray-900 ${
                selectedId === job.id ? "bg-gray-900" : ""
              }`}
            >
              <div className="flex items-center gap-2 mb-0.5">
                <span className={`text-xs px-1.5 py-0.5 rounded ${STATUS_COLORS[job.status] ?? "bg-gray-700 text-gray-300"}`}>
                  {job.status}
                </span>
                {job.relevance_score != null && (
                  <span className="text-xs text-purple-400">R:{job.relevance_score}</span>
                )}
                {job.trustworthiness_score != null && (
                  <span className="text-xs text-teal-400">T:{job.trustworthiness_score}</span>
                )}
                <span className="text-xs text-gray-500 ml-auto">{job.provider}</span>
              </div>
              <div className="font-medium text-sm truncate">{job.title ?? "(no title)"}</div>
              <div className="text-xs text-gray-400 truncate">
                {job.posted_company_name ?? "—"} · {job.country ?? "?"} · {job.remote_scope ?? "?"}
              </div>
            </button>
          ))}
        </div>
      </div>

      {/* Right pane: detail */}
      <div className="flex-1 overflow-y-auto p-4">
        {selected ? (
          <JobDetail jobId={selected.id} key={selected.id} />
        ) : (
          <div className="text-gray-600 text-sm mt-8 text-center">Select a job</div>
        )}
      </div>
    </>
  );
}
```

- [ ] **Step 5: Create `dashboard/app/components/JobDetail.tsx`**

```tsx
"use client";
import { useEffect, useState } from "react";
import { CommandButton } from "./CommandButton";
import { updateJobAction } from "../actions";

export function JobDetail({ jobId }: { jobId: number }) {
  const [data, setData] = useState<any | null>(null);
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState({ status: "", comment: "", current_interview_status: "" });

  useEffect(() => {
    fetch(`/api/jobs/${jobId}`)
      .then((r) => r.json())
      .then((d) => {
        setData(d);
        setForm({
          status: d.job.status,
          comment: d.job.comment ?? "",
          current_interview_status: d.job.current_interview_status ?? "",
        });
      });
  }, [jobId]);

  if (!data) return <div className="text-gray-500 text-sm">Loading…</div>;

  const { job, assessment, research, commands } = data;

  async function save() {
    await updateJobAction(jobId, form);
    setEditing(false);
  }

  return (
    <div className="space-y-4 max-w-2xl">
      <div>
        <h2 className="text-xl font-bold">{job.title ?? "(no title)"}</h2>
        <p className="text-gray-400 text-sm">{job.posted_company_name} · {job.country} · {job.remote_scope}</p>
        <div className="flex gap-2 mt-1 text-xs text-gray-500">
          <span>First seen: {job.first_seen?.slice(0, 10)}</span>
          <span>Last seen: {job.last_seen?.slice(0, 10)}</span>
          {job.apply_url && (
            <a href={job.apply_url} target="_blank" className="text-blue-400 underline">Apply</a>
          )}
        </div>
      </div>

      {assessment && (
        <div className="bg-gray-900 rounded p-3 space-y-1">
          <div className="font-semibold text-sm text-purple-300">Assessment</div>
          <div className="text-sm">Verdict: <span className="font-medium">{assessment.apply_verdict}</span></div>
          <div className="text-sm">Relevance: {assessment.relevance_score} · Summary: {assessment.one_line_summary}</div>
          {assessment.red_flag_scan && <div className="text-xs text-red-400">⚠ {assessment.red_flag_scan}</div>}
        </div>
      )}

      {research && (
        <div className="bg-gray-900 rounded p-3 space-y-1">
          <div className="font-semibold text-sm text-teal-300">Company Research</div>
          <div className="text-sm">Trust score: {research.trustworthiness_score}</div>
          {research.hiring_entity_type && <div className="text-xs text-yellow-400">{research.hiring_entity_type}</div>}
          {research.glassdoor_summary && <div className="text-xs text-gray-400">{research.glassdoor_summary}</div>}
          {research.research_notes && <div className="text-xs text-gray-400">{research.research_notes}</div>}
        </div>
      )}

      <div className="bg-gray-900 rounded p-3">
        <div className="font-semibold text-sm mb-2">Workflow</div>
        {editing ? (
          <div className="space-y-2">
            <select
              value={form.status}
              onChange={(e) => setForm({ ...form, status: e.target.value })}
              className="bg-gray-800 border border-gray-600 rounded px-2 py-1 text-sm w-full"
            >
              {["new","interesting","not_interested","researching","researched","draft_ready","applied","interviewing","rejected","archived"].map(s => (
                <option key={s} value={s}>{s}</option>
              ))}
            </select>
            <textarea
              value={form.comment}
              onChange={(e) => setForm({ ...form, comment: e.target.value })}
              placeholder="Comment..."
              className="bg-gray-800 border border-gray-600 rounded px-2 py-1 text-sm w-full h-16"
            />
            <input
              value={form.current_interview_status}
              onChange={(e) => setForm({ ...form, current_interview_status: e.target.value })}
              placeholder="Interview status..."
              className="bg-gray-800 border border-gray-600 rounded px-2 py-1 text-sm w-full"
            />
            <div className="flex gap-2">
              <button onClick={save} className="bg-green-700 hover:bg-green-600 rounded px-3 py-1 text-sm">Save</button>
              <button onClick={() => setEditing(false)} className="bg-gray-700 rounded px-3 py-1 text-sm">Cancel</button>
            </div>
          </div>
        ) : (
          <div className="space-y-1">
            <div className="text-sm">Status: <span className="font-medium">{job.status}</span></div>
            {job.comment && <div className="text-sm text-gray-400">{job.comment}</div>}
            {job.current_interview_status && <div className="text-xs text-gray-500">{job.current_interview_status}</div>}
            <button onClick={() => setEditing(true)} className="text-xs text-blue-400 underline mt-1">Edit</button>
          </div>
        )}
      </div>

      <CommandButton jobId={jobId} commands={commands} />

      {job.description && (
        <details className="bg-gray-900 rounded p-3">
          <summary className="text-sm font-semibold cursor-pointer">Description</summary>
          <p className="text-xs text-gray-400 mt-2 whitespace-pre-wrap">{job.description.slice(0, 3000)}</p>
        </details>
      )}
    </div>
  );
}
```

- [ ] **Step 6: Create `dashboard/app/components/CommandButton.tsx`**

```tsx
"use client";
import { useState } from "react";

const STATUS_COLOR: Record<string, string> = {
  pending: "text-yellow-400",
  running: "text-blue-400",
  succeeded: "text-green-400",
  failed: "text-red-400",
};

export function CommandButton({ jobId, commands }: { jobId: number; commands: any[] }) {
  const [triggering, setTriggering] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const latest = commands[0] ?? null;

  async function triggerResearch() {
    setTriggering(true);
    setError(null);
    try {
      const res = await fetch("/api/commands", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ command_type: "research_job", job_id: jobId }),
      });
      if (!res.ok) throw new Error(await res.text());
    } catch (e: any) {
      setError(e.message);
    } finally {
      setTriggering(false);
    }
  }

  const canTrigger = !latest || !["pending", "running"].includes(latest.status);

  return (
    <div className="bg-gray-900 rounded p-3 space-y-2">
      <div className="font-semibold text-sm">Research</div>
      {latest && (
        <div className="text-xs space-y-0.5">
          <span className={STATUS_COLOR[latest.status] ?? "text-gray-400"}>
            {latest.status}
          </span>
          {latest.finished_at && <span className="text-gray-500 ml-2">{latest.finished_at.slice(0, 16)}</span>}
          {latest.error && <div className="text-red-400">{latest.error}</div>}
        </div>
      )}
      <button
        onClick={triggerResearch}
        disabled={triggering || !canTrigger}
        className="bg-purple-700 hover:bg-purple-600 disabled:opacity-40 rounded px-3 py-1 text-sm"
      >
        {triggering ? "Queuing…" : "Research job"}
      </button>
      {error && <div className="text-xs text-red-400">{error}</div>}
    </div>
  );
}
```

- [ ] **Step 7: Create `dashboard/app/api/jobs/[id]/route.ts`**

```typescript
import { NextResponse } from "next/server";
import { getJobDetail } from "@/lib/db";

export async function GET(req: Request, { params }: { params: { id: string } }) {
  const id = parseInt(params.id);
  if (isNaN(id)) return NextResponse.json({ error: "Bad id" }, { status: 400 });
  const data = getJobDetail(id);
  if (!data) return NextResponse.json({ error: "Not found" }, { status: 404 });
  return NextResponse.json(data);
}
```

- [ ] **Step 8: Create `dashboard/app/api/commands/route.ts`**

```typescript
import { NextRequest, NextResponse } from "next/server";
import { createResearchCommand, getDb } from "@/lib/db";
import { spawn } from "child_process";
import path from "path";

const ALLOWED_COMMANDS = new Set(["research_job"]);

export async function POST(req: NextRequest) {
  const body = await req.json();
  const { command_type, job_id } = body;

  if (!ALLOWED_COMMANDS.has(command_type)) {
    return NextResponse.json({ error: "Command not allowed" }, { status: 400 });
  }
  if (!Number.isInteger(job_id)) {
    return NextResponse.json({ error: "Invalid job_id" }, { status: 400 });
  }

  const db = getDb();
  const job = db.prepare("SELECT id FROM jobs WHERE id = ?").get(job_id);
  if (!job) return NextResponse.json({ error: "Job not found" }, { status: 404 });

  const { commandId, existing } = createResearchCommand(job_id);

  if (!existing) {
    const scriptPath = path.resolve(process.cwd(), "../scripts/research_job.py");
    const dbPath = path.resolve(process.cwd(), "../jobs.db");
    const child = spawn("python3", [scriptPath, "--db", dbPath, "--job-id", String(job_id), "--command-id", String(commandId)], {
      detached: true,
      stdio: "ignore",
    });
    child.unref();
  }

  return NextResponse.json({ commandId, existing });
}
```

- [ ] **Step 9: Build and start the dev server**

```bash
cd /Users/zall/interviews/dashboard && npm run dev &
```

Visit `http://localhost:3000` in browser. Should show jobs from SQLite.

---

## Chunk 5: Research Worker

### Task 5: Research job script

**Files:**
- Create: `scripts/research_job.py`

**Note:** Requires `anthropic` Python package. Install if missing:
```bash
pip3 install anthropic
```

- [ ] **Step 1: Create `scripts/research_job.py`**

```python
#!/usr/bin/env python3
"""
Research a single job: company due diligence + job assessment.

Usage:
  python3 research_job.py --db jobs.db --job-id 123
  python3 research_job.py --db jobs.db --job-id 123 --command-id 456
"""
import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from db import get_connection, log_event

try:
    import anthropic
except ImportError:
    print("ERROR: anthropic package not installed. Run: pip3 install anthropic", file=sys.stderr)
    sys.exit(1)

MODEL = "claude-sonnet-4-6"
DB_PATH_DEFAULT = str(Path(__file__).parent.parent / "jobs.db")

RESEARCH_SYSTEM = """You are a job opportunity researcher. Given a job posting, you:
1. Assess the posting company's legitimacy, type (direct employer vs recruiter/agency), and trustworthiness.
2. Research company profile: founding year, HQ, employee count, funding, news, Glassdoor reputation.
3. Assess job fit: seniority, tech stack, remote eligibility, salary, visa/contract structure, AI-nativeness.
4. Produce a one-line verdict and relevance score (0-100) and trust score (0-100).

You MUST respond with valid JSON matching the schema exactly. Use "Not found" for missing fields, never omit keys.
Cite source URLs in source_urls. Do not infer hidden clients for recruiter posts.
"""

RESEARCH_SCHEMA = {
    "legitimacy_check": "string",
    "hiring_entity_type": "direct | recruiter | agency | intermediary | unknown",
    "founded_year": "integer or null",
    "hq_location": "string",
    "employee_count": "string",
    "headcount_trend": "string",
    "funding_summary": "string",
    "funding_stage": "string",
    "risk_news": "string",
    "glassdoor_summary": "string",
    "trustworthiness_score": "integer 0-100",
    "relevance_score": "integer 0-100",
    "apply_verdict": "Apply | Apply with caution | Skip",
    "one_line_summary": "string",
    "red_flag_scan": "string",
    "seniority_fit": "string",
    "tech_stack_fit": "string",
    "ic_or_management": "IC | Management | Both | Unknown",
    "salary_assessment": "string",
    "remote_eligibility": "string",
    "visa_contract_structure": "string",
    "ai_native_assessment": "string",
    "assessment_notes": "string",
    "research_notes": "string",
    "source_urls": ["url1", "url2"],
}


def _update_command(con, command_id: int, status: str, result_json: str | None = None, error: str | None = None):
    if status == "running":
        con.execute(
            "UPDATE agent_commands SET status='running', started_at=datetime('now') WHERE id=?",
            (command_id,)
        )
    else:
        con.execute(
            "UPDATE agent_commands SET status=?, finished_at=datetime('now'), result_json=?, error=? WHERE id=?",
            (status, result_json, error, command_id)
        )
    con.commit()


def research_job(db_path: str, job_id: int, command_id: int | None = None) -> int:
    con = get_connection(db_path)
    job = con.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    if not job:
        print(f"ERROR: job {job_id} not found", file=sys.stderr)
        if command_id:
            _update_command(con, command_id, "failed", error=f"job {job_id} not found")
        con.close()
        return 1

    if command_id:
        _update_command(con, command_id, "running")

    log_event(con, "job", job_id, "research_started", "research_job")
    con.commit()

    prompt = f"""Research this job posting:

Title: {job['title'] or 'Unknown'}
Company: {job['posted_company_name'] or 'Unknown'}
URL: {job['url']}
Apply URL: {job['apply_url'] or job['url']}
Location: {job['location'] or 'Unknown'} ({job['country'] or 'Unknown'})
Remote: {job['remote_scope'] or 'Unknown'}

Description (first 3000 chars):
{(job['description'] or '')[:3000]}

Respond ONLY with a JSON object matching this schema:
{json.dumps(RESEARCH_SCHEMA, indent=2)}
"""

    client = anthropic.Anthropic()
    try:
        message = client.messages.create(
            model=MODEL,
            max_tokens=4096,
            system=RESEARCH_SYSTEM,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = message.content[0].text
        # Strip markdown code blocks if present
        if raw.strip().startswith("```"):
            raw = raw.strip().split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        result = json.loads(raw)
    except json.JSONDecodeError as e:
        err = f"LLM returned invalid JSON: {e}"
        log_event(con, "job", job_id, "research_failed", "research_job", json.dumps({"error": err}))
        if command_id:
            _update_command(con, command_id, "failed", error=err)
        con.commit()
        con.close()
        return 1
    except Exception as e:
        err = str(e)
        log_event(con, "job", job_id, "research_failed", "research_job", json.dumps({"error": err}))
        if command_id:
            _update_command(con, command_id, "failed", error=err)
        con.commit()
        con.close()
        return 1

    # Upsert company_research
    company_id = job["company_id"]
    if company_id:
        existing_research = con.execute(
            "SELECT id FROM company_research WHERE company_id = ?", (company_id,)
        ).fetchone()
        if not existing_research:
            con.execute("""
                INSERT INTO company_research (
                    company_id, researched_at, research_status,
                    legitimacy_check, hiring_entity_type, founded_year,
                    hq_location, employee_count, headcount_trend,
                    funding_summary, funding_stage, risk_news,
                    glassdoor_summary, trustworthiness_score,
                    research_notes, source_urls_json, raw_research_json
                ) VALUES (?,datetime('now'),'researched',?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                company_id,
                result.get("legitimacy_check"), result.get("hiring_entity_type"),
                result.get("founded_year"), result.get("hq_location"),
                result.get("employee_count"), result.get("headcount_trend"),
                result.get("funding_summary"), result.get("funding_stage"),
                result.get("risk_news"), result.get("glassdoor_summary"),
                result.get("trustworthiness_score"), result.get("research_notes"),
                json.dumps(result.get("source_urls", [])), json.dumps(result),
            ))

    # Upsert job_assessments
    existing_assessment = con.execute(
        "SELECT id FROM job_assessments WHERE job_id = ?", (job_id,)
    ).fetchone()
    if existing_assessment:
        con.execute("""
            UPDATE job_assessments SET
                assessed_at=datetime('now'), assessment_status='researched',
                relevance_score=?, apply_verdict=?, one_line_summary=?,
                red_flag_scan=?, seniority_fit=?, tech_stack_fit=?,
                ic_or_management=?, salary_assessment=?, remote_eligibility=?,
                visa_contract_structure=?, ai_native_assessment=?,
                assessment_notes=?, source_urls_json=?, raw_assessment_json=?,
                updated_at=datetime('now')
            WHERE job_id=?
        """, (
            result.get("relevance_score"), result.get("apply_verdict"),
            result.get("one_line_summary"), result.get("red_flag_scan"),
            result.get("seniority_fit"), result.get("tech_stack_fit"),
            result.get("ic_or_management"), result.get("salary_assessment"),
            result.get("remote_eligibility"), result.get("visa_contract_structure"),
            result.get("ai_native_assessment"), result.get("assessment_notes"),
            json.dumps(result.get("source_urls", [])), json.dumps(result),
            job_id,
        ))
    else:
        con.execute("""
            INSERT INTO job_assessments (
                job_id, assessed_at, assessment_status,
                relevance_score, apply_verdict, one_line_summary,
                red_flag_scan, seniority_fit, tech_stack_fit,
                ic_or_management, salary_assessment, remote_eligibility,
                visa_contract_structure, ai_native_assessment,
                assessment_notes, source_urls_json, raw_assessment_json
            ) VALUES (?,datetime('now'),'researched',?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            job_id,
            result.get("relevance_score"), result.get("apply_verdict"),
            result.get("one_line_summary"), result.get("red_flag_scan"),
            result.get("seniority_fit"), result.get("tech_stack_fit"),
            result.get("ic_or_management"), result.get("salary_assessment"),
            result.get("remote_eligibility"), result.get("visa_contract_structure"),
            result.get("ai_native_assessment"), result.get("assessment_notes"),
            json.dumps(result.get("source_urls", [])), json.dumps(result),
        ))

    con.execute(
        "UPDATE jobs SET status='researched', updated_at=datetime('now') WHERE id=?",
        (job_id,)
    )
    log_event(con, "job", job_id, "research_complete", "research_job",
              json.dumps({"verdict": result.get("apply_verdict"), "score": result.get("relevance_score")}))
    if command_id:
        _update_command(con, command_id, "succeeded", result_json=json.dumps({
            "verdict": result.get("apply_verdict"),
            "relevance_score": result.get("relevance_score"),
            "trustworthiness_score": result.get("trustworthiness_score"),
            "one_line_summary": result.get("one_line_summary"),
        }))
    con.commit()
    con.close()
    print(f"Research complete: {result.get('apply_verdict')} R:{result.get('relevance_score')} T:{result.get('trustworthiness_score')}")
    return 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default=DB_PATH_DEFAULT)
    parser.add_argument("--job-id", type=int, required=True)
    parser.add_argument("--command-id", type=int)
    args = parser.parse_args()
    sys.exit(research_job(args.db, args.job_id, args.command_id))


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Install anthropic SDK if needed**

```bash
pip3 install anthropic
```

- [ ] **Step 3: Smoke test against a real job in the DB**

```bash
cd /Users/zall/interviews && python3 scripts/research_job.py --db jobs.db --job-id 1
```
Expected: `Research complete: Apply/Apply with caution/Skip R:XX T:XX`

---

## Chunk 6: Light Tagging + Hermes Daily Pipeline

### Task 6: Light tagging script

**Files:**
- Create: `scripts/tag_new_jobs.py`

- [ ] **Step 1: Create `scripts/tag_new_jobs.py`**

```python
#!/usr/bin/env python3
"""
Apply cheap non-AI tags to newly inserted jobs.
Tags are stored in source_payload_json (merge) and as light hints only.
Never suppresses, archives, or deletes jobs.

Usage:
  python3 tag_new_jobs.py --db jobs.db [--since-hours 25]
"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from db import get_connection

ROLE_KEYWORDS = {
    "engineering_manager": ["engineering manager", "em ", "head of engineering", "vp engineering"],
    "ai_engineer": ["ai engineer", "ml engineer", "machine learning", "llm", "generative ai"],
    "backend": ["backend", "back-end", "server-side", "api engineer", "platform engineer"],
    "frontend": ["frontend", "front-end", "react", "vue", "angular", "ui engineer"],
    "fullstack": ["full stack", "fullstack", "full-stack"],
    "staff_plus": ["staff engineer", "principal engineer", "distinguished engineer"],
}

SENIORITY_KEYWORDS = {
    "senior": ["senior", "sr.", "sr ", "lead"],
    "staff_plus": ["staff", "principal", "distinguished", "fellow"],
    "manager": ["manager", "director", "vp ", "head of"],
    "mid": ["mid-level", "mid level"],
    "junior": ["junior", "jr.", "jr ", "graduate", "entry level"],
}

AI_KEYWORDS = ["llm", "gpt", "ai", "machine learning", "generative", "rag", "vector", "embedding", "anthropic", "openai"]
RECRUITER_KEYWORDS = ["via recruiter", "recruiting", " agency", "talent acquisition", "staffing"]


def classify(title: str, description: str) -> dict:
    text = f"{title} {description}".lower()
    title_lower = title.lower()

    role = "other"
    for r, kws in ROLE_KEYWORDS.items():
        if any(k in text for k in kws):
            role = r
            break

    seniority = "unknown"
    for s, kws in SENIORITY_KEYWORDS.items():
        if any(k in title_lower for k in kws):
            seniority = s
            break

    ai_relevant = any(k in text for k in AI_KEYWORDS)
    recruiter_hint = any(k in text for k in RECRUITER_KEYWORDS)

    remote_signal = "unknown"
    if "fully remote" in text or "100% remote" in text:
        remote_signal = "fully_remote"
    elif "remote" in text and "hybrid" in text:
        remote_signal = "hybrid"
    elif "remote" in text:
        remote_signal = "remote"
    elif "on-site" in text or "onsite" in text:
        remote_signal = "onsite"

    salary_missing = not bool(re.search(r"\$[\d,]+|\€[\d,]+|[\d,]+k|\bsalary\b", text))

    return {
        "light_role": role,
        "light_seniority": seniority,
        "light_ai_relevant": ai_relevant,
        "light_remote_signal": remote_signal,
        "light_salary_missing": salary_missing,
        "light_recruiter_hint": recruiter_hint,
    }


def tag_new_jobs(db_path: str, since_hours: int = 25) -> dict:
    con = get_connection(db_path)
    jobs = con.execute(
        "SELECT id, title, description, source_payload_json FROM jobs "
        "WHERE first_seen >= datetime('now', ?)",
        (f"-{since_hours} hours",)
    ).fetchall()

    tagged = 0
    for job in jobs:
        tags = classify(job["title"] or "", job["description"] or "")
        existing = {}
        if job["source_payload_json"]:
            try:
                existing = json.loads(job["source_payload_json"])
            except Exception:
                pass
        existing.update(tags)
        con.execute(
            "UPDATE jobs SET source_payload_json=?, updated_at=datetime('now') WHERE id=?",
            (json.dumps(existing), job["id"])
        )
        tagged += 1

    con.commit()
    con.close()
    return {"tagged": tagged}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", required=True)
    parser.add_argument("--since-hours", type=int, default=25)
    args = parser.parse_args()
    result = tag_new_jobs(args.db, args.since_hours)
    print(f"Tagged {result['tagged']} jobs")


if __name__ == "__main__":
    main()
```

### Task 7: Telegram notification helper

**Files:**
- Create: `scripts/telegram_notify.py`

- [ ] **Step 1: Create `scripts/telegram_notify.py`**

```python
#!/usr/bin/env python3
"""
Send Telegram notifications via hermes send.

Usage:
  python3 telegram_notify.py --type daily_digest --db jobs.db --run-id 5
  python3 telegram_notify.py --type research_complete --job-id 12 --db jobs.db
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from db import get_connection

HERMES = str(Path.home() / ".local/bin/hermes")
TELEGRAM_TARGET = "telegram"


def _send(message: str) -> None:
    result = subprocess.run(
        [HERMES, "send", "--to", TELEGRAM_TARGET, message],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"Telegram send failed: {result.stderr}", file=sys.stderr)


def daily_digest(db_path: str, run_id: int) -> None:
    con = get_connection(db_path)
    run = con.execute("SELECT * FROM pipeline_runs WHERE id = ?", (run_id,)).fetchone()
    if not run:
        _send("Daily jobs run: pipeline_run not found")
        return

    summary = {}
    if run["summary_json"]:
        try:
            summary = json.loads(run["summary_json"])
        except Exception:
            pass

    inserted = summary.get("inserted", 0)
    failed = summary.get("failed", 0)
    status_emoji = "✅" if run["status"] == "succeeded" else ("⚠️" if run["status"] == "partial" else "❌")

    lines = [
        f"{status_emoji} Daily jobs run: {run['status']}",
        f"New jobs: {inserted}",
    ]

    if inserted == 0 and failed == 0:
        lines.append("All providers OK. No new jobs.")
    elif inserted > 0:
        new_jobs = con.execute(
            "SELECT j.title, j.posted_company_name, j.country, j.url "
            "FROM jobs j "
            "WHERE j.first_seen >= datetime('now', '-25 hours') "
            "ORDER BY j.first_seen DESC LIMIT 20"
        ).fetchall()
        lines.append("\nNew jobs:")
        for job in new_jobs:
            lines.append(f"• {job['title'] or '?'} @ {job['posted_company_name'] or '?'} ({job['country'] or '?'})")

    if failed > 0:
        lines.append(f"\n⚠️ Failed items: {failed}")

    con.close()
    _send("\n".join(lines))


def pipeline_failure(provider: str, step: str, error: str, artifact_path: str) -> None:
    msg = (
        f"❌ Job pipeline failure\n"
        f"Provider/step: {provider} {step}\n"
        f"Error: {error[:200]}\n"
        f"Artifacts/logs: {artifact_path}\n"
        f"Action: fix scraper with Codex before next run"
    )
    _send(msg)


def research_complete(db_path: str, job_id: int) -> None:
    con = get_connection(db_path)
    job = con.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    assessment = con.execute(
        "SELECT * FROM job_assessments WHERE job_id = ?", (job_id,)
    ).fetchone()
    research = con.execute(
        "SELECT cr.trustworthiness_score FROM company_research cr "
        "JOIN jobs j ON j.company_id = cr.company_id WHERE j.id = ?", (job_id,)
    ).fetchone()
    con.close()

    if not job or not assessment:
        _send(f"Research complete for job {job_id} (no details available)")
        return

    trust = research["trustworthiness_score"] if research else "?"
    msg = (
        f"🔬 Research complete\n"
        f"{job['title'] or '?'} - {job['posted_company_name'] or '?'}\n"
        f"Verdict: {assessment['apply_verdict'] or '?'}\n"
        f"Relevance: {assessment['relevance_score'] or '?'}\n"
        f"Trust: {trust}\n"
        f"Summary: {assessment['one_line_summary'] or '?'}\n"
        f"Source: {job['apply_url'] or job['url']}\n"
        f"Dashboard: http://localhost:3000"
    )
    _send(msg)


def research_failed(db_path: str, job_id: int, error: str) -> None:
    con = get_connection(db_path)
    job = con.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    con.close()
    title = job["title"] if job else f"job {job_id}"
    company = job["posted_company_name"] if job else "?"
    msg = (
        f"❌ Research failed\n"
        f"{title} - {company}\n"
        f"Error: {error[:200]}\n"
        f"Dashboard: http://localhost:3000\n"
        f"Action: inspect command error and rerun from dashboard"
    )
    _send(msg)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--type", required=True,
                        choices=["daily_digest", "pipeline_failure", "research_complete", "research_failed"])
    parser.add_argument("--db")
    parser.add_argument("--run-id", type=int)
    parser.add_argument("--job-id", type=int)
    parser.add_argument("--provider")
    parser.add_argument("--step")
    parser.add_argument("--error")
    parser.add_argument("--artifact-path")
    args = parser.parse_args()

    if args.type == "daily_digest":
        daily_digest(args.db, args.run_id)
    elif args.type == "pipeline_failure":
        pipeline_failure(args.provider or "?", args.step or "?",
                         args.error or "unknown", args.artifact_path or "?")
    elif args.type == "research_complete":
        research_complete(args.db, args.job_id)
    elif args.type == "research_failed":
        research_failed(args.db, args.job_id, args.error or "unknown")


if __name__ == "__main__":
    main()
```

### Task 8: Hermes daily pipeline skill + cron job

**Files:**
- Create: `.codex/skills/daily-pipeline/SKILL.md`

- [ ] **Step 1: Create `.codex/skills/daily-pipeline/SKILL.md`**

```markdown
---
name: daily-pipeline
description: Use when running the autonomous daily job pipeline. Scrapes greenhouse and jobleads, ingests into SQLite, tags new jobs, and sends Telegram digest.
---

# Daily Job Pipeline

## Overview

Run the full daily job pipeline for the autonomous job search system.

Work directory: `/Users/zall/interviews`
DB: `/Users/zall/interviews/jobs.db`

## Pipeline Steps

### Step 1: Record pipeline start

```bash
python3 -c "
import sys; sys.path.insert(0, 'scripts')
from db import get_connection, create_pipeline_run
con = get_connection('jobs.db')
run_id = create_pipeline_run(con, 'daily_pipeline')
con.commit()
print(run_id)
" > /tmp/hermes_pipeline_run_id.txt
```

Run ID is saved to `/tmp/hermes_pipeline_run_id.txt` for use in Step 6.

### Step 2: Scrape Greenhouse

Use the `greenhouse-daily-export` skill to scrape and save:
`outputs/greenhouse/runs/greenhouse_jobs_live_YYYY-MM-DD.json`

If this step fails, record the failure and continue to JobLeads.

### Step 3: Scrape JobLeads

Use the `jobleads-daily-export` skill to scrape and save:
`outputs/jobleads/runs/jobleads_jobs_live_YYYY-MM-DD.json`

If this step fails, record the failure and continue.

### Step 4: Ingest successful artifacts

```bash
python3 scripts/ingest_provider_outputs.py --db jobs.db --all-latest
```

### Step 5: Tag new jobs

```bash
python3 scripts/tag_new_jobs.py --db jobs.db --since-hours 25
```

### Step 6: Send Telegram digest

```bash
RUNID=$(cat /tmp/hermes_pipeline_run_id.txt)
python3 scripts/telegram_notify.py --type daily_digest --db jobs.db --run-id "$RUNID"
```

## Failure Handling

If a provider scraper fails:

```bash
python3 scripts/telegram_notify.py \
  --type pipeline_failure \
  --provider <provider_name> \
  --step scrape \
  --error "<short error>" \
  --artifact-path "outputs/<provider>/runs/"
```

Continue with remaining steps.

## Output

Pipeline run is recorded in `pipeline_runs` table.
All new jobs are visible in the dashboard at `http://localhost:3000`.
Telegram digest is sent to configured channel.
```

- [ ] **Step 2: Create the Hermes cron job**

```bash
hermes cron create "0 9 * * *" \
  "Run the daily job pipeline: scrape greenhouse and jobleads, ingest into jobs.db, tag new jobs, send Telegram digest. Follow the daily-pipeline skill exactly." \
  --name "daily-jobs-pipeline" \
  --skill daily-pipeline \
  --skill greenhouse-daily-export \
  --skill jobleads-daily-export \
  --deliver telegram \
  --workdir /Users/zall/interviews
```

- [ ] **Step 3: Verify cron job registered**

```bash
hermes cron list
```
Expected: `daily-jobs-pipeline` listed with `0 9 * * *` schedule.

---

## Chunk 7: End-to-End Verification

### Task 9: Full smoke test

- [ ] **Step 1: Run all Python tests**

```bash
cd /Users/zall/interviews/scripts && python3 -m pytest test_db.py test_ingestion.py -v
```
Expected: All tests pass.

- [ ] **Step 2: Verify DB has jobs**

```bash
cd /Users/zall/interviews && python3 -c "
import sys; sys.path.insert(0, 'scripts')
from db import get_connection
con = get_connection('jobs.db')
print('Jobs:', con.execute('SELECT COUNT(*) FROM jobs').fetchone()[0])
print('Companies:', con.execute('SELECT COUNT(*) FROM companies').fetchone()[0])
print('Providers:', [r[0] for r in con.execute('SELECT DISTINCT provider FROM jobs').fetchall()])
"
```
Expected: Non-zero job count, greenhouse + jobleads providers.

- [ ] **Step 3: Verify dashboard loads**

Ensure `http://localhost:3000` shows job list. Click a job — detail pane opens. Click "Research job" — command queued.

- [ ] **Step 4: Dry-run pipeline failure Telegram**

```bash
cd /Users/zall/interviews && python3 scripts/telegram_notify.py \
  --type pipeline_failure \
  --provider greenhouse \
  --step scrape \
  --error "test error" \
  --artifact-path "outputs/greenhouse/runs/"
```
Expected: Telegram DM received.

- [ ] **Step 5: Test manual cron run** (optional — triggers scraper)

```bash
hermes cron run daily-jobs-pipeline
```
