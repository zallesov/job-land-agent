# Pipeline & Status Redesign Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace `sanity_check_job` with `screen_job` (writes full lightweight assessment to DB), remove auto-research from pipeline, simplify `jobs.status` to linear pipeline stages, and update the dashboard to match.

**Architecture:** Four independent change streams executed in order: (1) new `screen_job` Python step + Hermes skill, (2) pipeline orchestration + `research_job` updates, (3) DB migration, (4) dashboard. Column drop comes last after `research_job` no longer writes the dropped columns.

**Tech Stack:** Python 3, SQLite (`scripts/db.py` helpers), Hermes (LLM agent), Next.js App Router, better-sqlite3, TypeScript.

**Spec:** `docs/superpowers/specs/2026-05-22-pipeline-status-redesign-design.md`

---

## Chunk 1: `screen_job` Python step + Hermes skill

### Task 1: Create `skills/screen-job/SKILL.md`

**Files:**
- Create: `skills/screen-job/SKILL.md`

- [ ] **Step 1: Write the skill file**

```markdown
# screen-job

Screen a job against the candidate's profile and produce a lightweight assessment.

## Input

`Use skill screen-job. job_id: 42. cv_path: /path/to/cv.md`

## Task

1. Read the CV from cv_path
2. Read the job from the database using job_id (use your DB read tools). Fields: title, description, company name, location, remote_scope, salary_range.
3. Assess the job against the candidate's profile. Evaluate ALL of the following:
   - **apply_verdict**: one of "Strong Apply" | "Apply with Caution" | "Need Research" | "Skip"
     - "Strong Apply": clear match — right seniority, tech stack, remote, no red flags
     - "Apply with Caution": worth applying but notable caveats (borderline tech fit, unclear remote, no salary info)
     - "Need Research": potentially interesting but cannot assess without more context (no description, vague company, unclear remote policy)
     - "Skip": hard disqualifiers — on-site only, junior/entry-level, completely unrelated domain, requires relocation outside target list (Berlin, Spain, EU remote)
   - **relevance_score**: 0–100 based on tech stack fit, seniority match, remote eligibility, domain relevance
   - **one_line_summary**: one sentence describing the role and fit
   - **seniority_fit**: brief note on level match
   - **tech_stack_fit**: brief note on tech overlap with candidate's profile
   - **remote_eligibility**: what the job says about remote; candidate target is EU remote / Berlin / Spain
   - **salary_assessment**: posted salary or "Not disclosed" if absent

## Output

Respond with a single JSON block. No prose.

```json
{
  "status": "success",
  "apply_verdict": "Strong Apply",
  "relevance_score": 85,
  "one_line_summary": "Senior backend Python role, fully remote EU, great stack fit",
  "seniority_fit": "Senior IC, matches target level",
  "tech_stack_fit": "Python, Postgres, Kafka — strong overlap",
  "remote_eligibility": "Fully remote, EU timezone",
  "salary_assessment": "€90k–120k posted"
}
```

Failure (cannot read job or CV):
```json
{"status": "failure", "error": "could not load job description"}
```

## Rules
- apply_verdict is always one of the four exact strings above
- relevance_score must be an integer 0–100
- Do NOT research the company — assess only from the job description and CV
- If description is missing or too short to assess, use verdict "Need Research"
```

- [ ] **Step 2: Verify file exists**

```bash
ls skills/screen-job/SKILL.md
```

- [ ] **Step 3: Commit**

```bash
git add skills/screen-job/SKILL.md
git commit -m "feat: add screen-job Hermes skill"
```

---

### Task 2: Write `screen_job.py` with tests

**Files:**
- Create: `scripts/pipeline/screen_job.py`
- Create: `tests/pipeline/test_screen_job.py`
- Modify: `scripts/db.py` (check if `update_job_status` supports `screen_failed`)

- [ ] **Step 1: Write failing tests**

Create `tests/pipeline/test_screen_job.py`:

```python
from unittest.mock import patch
from scripts.pipeline.types import HermesResult
from scripts.db import get_connection


def _insert_job(con, status="enriched", description="We need a senior Python engineer..."):
    jid = con.execute(
        "INSERT INTO jobs (url, provider, status, title, description) VALUES (?,?,?,?,?)",
        ("http://x.com", "gh", status, "Senior Python Engineer", description)
    ).lastrowid
    con.commit()
    return jid


STRONG_APPLY_RESULT = HermesResult(
    success=True,
    data={
        "status": "success",
        "apply_verdict": "Strong Apply",
        "relevance_score": 90,
        "one_line_summary": "Great fit",
        "seniority_fit": "Senior IC",
        "tech_stack_fit": "Python match",
        "remote_eligibility": "Remote EU",
        "salary_assessment": "€100k",
    },
    error=None, raw_output="",
)

SKIP_RESULT = HermesResult(
    success=True,
    data={
        "status": "success",
        "apply_verdict": "Skip",
        "relevance_score": 5,
        "one_line_summary": "On-site junior role",
        "seniority_fit": "Junior, does not match",
        "tech_stack_fit": "No overlap",
        "remote_eligibility": "On-site only",
        "salary_assessment": "Not disclosed",
    },
    error=None, raw_output="",
)


@patch("scripts.pipeline.screen_job.hermes_call")
def test_strong_apply_sets_screened_and_writes_assessment(mock_hermes, db_path, con):
    mock_hermes.return_value = STRONG_APPLY_RESULT
    jid = _insert_job(con)
    from scripts.pipeline.screen_job import screen_job
    result = screen_job(jid, db_path=db_path)
    assert result.success is True
    row = con.execute("SELECT status FROM jobs WHERE id = ?", (jid,)).fetchone()
    assert row["status"] == "screened"
    assessment = con.execute("SELECT * FROM job_assessments WHERE job_id = ?", (jid,)).fetchone()
    assert assessment is not None
    assert assessment["apply_verdict"] == "Strong Apply"
    assert assessment["relevance_score"] == 90
    assert assessment["assessment_status"] == "screened"


@patch("scripts.pipeline.screen_job.hermes_call")
def test_skip_verdict_still_sets_screened_status(mock_hermes, db_path, con):
    mock_hermes.return_value = SKIP_RESULT
    jid = _insert_job(con)
    from scripts.pipeline.screen_job import screen_job
    screen_job(jid, db_path=db_path)
    row = con.execute("SELECT status FROM jobs WHERE id = ?", (jid,)).fetchone()
    assert row["status"] == "screened"
    assessment = con.execute("SELECT apply_verdict FROM job_assessments WHERE job_id = ?", (jid,)).fetchone()
    assert assessment["apply_verdict"] == "Skip"


@patch("scripts.pipeline.screen_job.hermes_call")
def test_hermes_failure_sets_screen_failed(mock_hermes, db_path, con):
    mock_hermes.return_value = HermesResult(
        success=False, data={}, error="timeout", raw_output="",
    )
    jid = _insert_job(con)
    from scripts.pipeline.screen_job import screen_job
    screen_job(jid, db_path=db_path)
    row = con.execute("SELECT status FROM jobs WHERE id = ?", (jid,)).fetchone()
    assert row["status"] == "screen_failed"


@patch("scripts.pipeline.screen_job.hermes_call")
def test_upsert_does_not_duplicate_assessment(mock_hermes, db_path, con):
    mock_hermes.return_value = STRONG_APPLY_RESULT
    jid = _insert_job(con)
    from scripts.pipeline.screen_job import screen_job
    screen_job(jid, db_path=db_path)
    screen_job(jid, db_path=db_path)
    count = con.execute("SELECT COUNT(*) FROM job_assessments WHERE job_id = ?", (jid,)).fetchone()[0]
    assert count == 1
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/zall/interviews && python -m pytest tests/pipeline/test_screen_job.py -v
```

Expected: `ImportError` or `ModuleNotFoundError` for `screen_job`

- [ ] **Step 3: Write `scripts/pipeline/screen_job.py`**

```python
from __future__ import annotations
from pathlib import Path

from .hermes import hermes_call, CV_PATH
from .types import HermesResult
from scripts.db import get_connection, update_job_status

_DEFAULT_DB = str(Path(__file__).parent.parent.parent / "jobs.db")


def screen_job(job_id: int, db_path: str = _DEFAULT_DB) -> HermesResult:
    con = get_connection(db_path)
    try:
        result = hermes_call(
            "screen-job",
            {"job_id": job_id, "cv_path": str(CV_PATH)},
        )
        if result.success:
            data = result.data
            _upsert_assessment(con, job_id, data)
            update_job_status(con, job_id, "screened")
            con.commit()
        else:
            update_job_status(con, job_id, "screen_failed", comment=result.error)
            con.commit()
    finally:
        con.close()
    return result


def _upsert_assessment(con, job_id: int, data: dict) -> None:
    existing = con.execute(
        "SELECT id FROM job_assessments WHERE job_id = ?", (job_id,)
    ).fetchone()
    fields = (
        data.get("apply_verdict"),
        data.get("relevance_score"),
        data.get("one_line_summary"),
        data.get("seniority_fit"),
        data.get("tech_stack_fit"),
        data.get("remote_eligibility"),
        data.get("salary_assessment"),
    )
    if existing:
        con.execute("""
            UPDATE job_assessments SET
                assessed_at = datetime('now'),
                assessment_status = 'screened',
                apply_verdict = ?, relevance_score = ?,
                one_line_summary = ?, seniority_fit = ?,
                tech_stack_fit = ?, remote_eligibility = ?,
                salary_assessment = ?,
                updated_at = datetime('now')
            WHERE job_id = ?
        """, fields + (job_id,))
    else:
        con.execute("""
            INSERT INTO job_assessments (
                job_id, assessed_at, assessment_status,
                apply_verdict, relevance_score, one_line_summary,
                seniority_fit, tech_stack_fit, remote_eligibility, salary_assessment
            ) VALUES (?, datetime('now'), 'screened', ?, ?, ?, ?, ?, ?, ?)
        """, (job_id,) + fields)
```

- [ ] **Step 4: Run tests — expect pass**

```bash
python -m pytest tests/pipeline/test_screen_job.py -v
```

Expected: 4 PASSED

- [ ] **Step 5: Commit**

```bash
git add scripts/pipeline/screen_job.py tests/pipeline/test_screen_job.py
git commit -m "feat: add screen_job pipeline step with assessment write"
```

---

## Chunk 2: Pipeline orchestration + `research_job` + `notify`

### Task 3: Update `scraping_pipeline.py`

**Files:**
- Modify: `scripts/scraping_pipeline.py`
- Modify: `tests/test_scraping_pipeline.py`

- [ ] **Step 1: Read existing pipeline test to understand mock patterns**

```bash
cat tests/test_scraping_pipeline.py
```

- [ ] **Step 2: Update `scraping_pipeline.py`**

In `scraping_pipeline.py`:
- Replace `from scripts.pipeline.sanity_check_job import sanity_check_job` → `from scripts.pipeline.screen_job import screen_job`
- Replace `sanity_check_job` call → `screen_job`
- Rename local variable `sanity_failures` → `screen_failures` everywhere
- Remove `_queue_research()` function entirely
- Remove `_queue_research(job_ids, db_path=db_path)` call at bottom of `run()`
- Remove `queued` variable and its print
- Update `send_daily_digest(enrich_failures=..., sanity_failures=...)` → `send_daily_digest(enrich_failures=..., screen_failures=...)`
- Update `print` at end: remove `research_queued=...`
- Change ingest status: in `ingest_jobs`, confirm jobs start with `new` (check `scripts/pipeline/ingest.py` — if it writes `listed`, update to `new`)

- [ ] **Step 3: Update `scripts/pipeline/types.py` and `ingest.py` to use `new` instead of `listed`**

`ShallowJob.status` defaults to `"listed"` in `types.py` — this must change to `"new"`.

```bash
grep -n "listed" scripts/pipeline/types.py scripts/pipeline/ingest.py
```

In `scripts/pipeline/types.py`, change the `status` field default from `"listed"` to `"new"`.
In `scripts/pipeline/ingest.py`, change any hardcoded `'listed'` to `'new'`.

- [ ] **Step 4: Update pipeline tests**

In `tests/test_scraping_pipeline.py`, rename all `sanity_check_job` references to `screen_job`, rename `sanity_failures` → `screen_failures`, remove `_queue_research` assertions.

- [ ] **Step 5: Run pipeline tests**

```bash
python -m pytest tests/test_scraping_pipeline.py -v
```

Expected: all PASSED

- [ ] **Step 6: Commit**

```bash
git add scripts/scraping_pipeline.py scripts/pipeline/ingest.py tests/test_scraping_pipeline.py
git commit -m "refactor: replace sanity_check_job with screen_job, remove auto-research from pipeline"
```

---

### Task 4: Update `notify.py`

**Files:**
- Modify: `scripts/pipeline/notify.py`
- Modify: `tests/pipeline/test_notify.py`

- [ ] **Step 1: Update `notify.py`**

Rename parameter `sanity_failures` → `screen_failures` and update message text `"Sanity check failed"` → `"Screen failed"`:

```python
def send_daily_digest(
    enrich_failures: list[tuple[int, str]] | None = None,
    screen_failures: list[tuple[int, str]] | None = None,
) -> None:
    enrich_failures = enrich_failures or []
    screen_failures = screen_failures or []
    if not enrich_failures and not screen_failures:
        return
    lines = ["Pipeline completed with failures"]
    if enrich_failures:
        lines.append(f"Enrich failed: {len(enrich_failures)} job(s)")
        for jid, err in enrich_failures[:5]:
            lines.append(f"  - job {jid}: {err[:60]}")
    if screen_failures:
        lines.append(f"Screen failed: {len(screen_failures)} job(s)")
        for jid, err in screen_failures[:5]:
            lines.append(f"  - job {jid}: {err[:60]}")
    telegram_notify("\n".join(lines))
```

- [ ] **Step 2: Update `tests/pipeline/test_notify.py`** — rename `sanity_failures` → `screen_failures`

- [ ] **Step 3: Run notify tests**

```bash
python -m pytest tests/pipeline/test_notify.py -v
```

Expected: all PASSED

- [ ] **Step 4: Commit**

```bash
git add scripts/pipeline/notify.py tests/pipeline/test_notify.py
git commit -m "refactor: rename sanity_failures to screen_failures in notify"
```

---

### Task 5: Update `research_job.py`

**Files:**
- Modify: `scripts/research_job.py`

- [ ] **Step 1: Update `SCHEMA_DESCRIPTION` — change `apply_verdict` enum**

Find line with `"apply_verdict": "Apply | Apply with caution | Skip"` and replace with:

```
  "apply_verdict": "Strong Apply | Apply with Caution | Skip",
```

- [ ] **Step 2: Add `status='researching'` write before LLM call**

Find the `client = anthropic.Anthropic()` line in `research_job()`. Immediately before it, add:

```python
    con.execute(
        "UPDATE jobs SET status='researching', updated_at=datetime('now') WHERE id=?",
        (job_id,)
    )
    con.commit()
```

- [ ] **Step 3: Remove dropped columns from `job_assessments` upsert**

In the `assessment_params` tuple, remove: `result.get("ic_or_management")`, `result.get("visa_contract_structure")`, `result.get("ai_native_assessment")`, `result.get("assessment_notes")`, `result.get("source_urls", [])` (source_urls_json), `json.dumps(result)` (raw_assessment_json).

Updated `assessment_params`:
```python
assessment_params = (
    result.get("relevance_score"), result.get("apply_verdict"),
    result.get("one_line_summary"), result.get("red_flag_scan"),
    result.get("seniority_fit"), result.get("tech_stack_fit"),
    result.get("salary_assessment"), result.get("remote_eligibility"),
)
```

Update both the `UPDATE` and `INSERT` SQL statements to match — remove the dropped columns from column lists and `?` placeholders.

Updated `UPDATE`:
```sql
UPDATE job_assessments SET
    assessed_at=datetime('now'), assessment_status='researched',
    relevance_score=?, apply_verdict=?, one_line_summary=?,
    red_flag_scan=?, seniority_fit=?, tech_stack_fit=?,
    salary_assessment=?, remote_eligibility=?,
    updated_at=datetime('now')
WHERE job_id=?
```

Updated `INSERT`:
```sql
INSERT INTO job_assessments (
    job_id, assessed_at, assessment_status,
    relevance_score, apply_verdict, one_line_summary,
    red_flag_scan, seniority_fit, tech_stack_fit,
    salary_assessment, remote_eligibility
) VALUES (?,datetime('now'),'researched',?,?,?,?,?,?,?,?)
```

- [ ] **Step 4: Smoke-test the file parses**

```bash
python -c "import scripts.research_job; print('OK')"
```

Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add scripts/research_job.py
git commit -m "refactor: update research_job — add researching status, new apply_verdict enum, remove dropped columns"
```

---

## Chunk 3: DB Migration

### Task 6: Write and run status migration

**Files:**
- Create: `scripts/migrate_pipeline_statuses.py`

- [ ] **Step 1: Write migration script**

```python
#!/usr/bin/env python3
"""
One-time migration: align jobs.status to new pipeline-stage values.
Run ONCE after all code is updated.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from scripts.db import get_connection

DB_PATH = str(Path(__file__).parent.parent / "jobs.db")


def migrate(db_path: str = DB_PATH) -> None:
    con = get_connection(db_path)
    try:
        # listed → new (jobs that were never enriched)
        r = con.execute("UPDATE jobs SET status='new' WHERE status='listed'")
        print(f"listed → new: {r.rowcount} rows")

        # skip and not_interested → screened (verdict captured in apply_verdict)
        r = con.execute("UPDATE jobs SET status='screened' WHERE status IN ('skip','not_interested')")
        print(f"skip/not_interested → screened: {r.rowcount} rows")

        # sanity_failed → screen_failed
        r = con.execute("UPDATE jobs SET status='screen_failed' WHERE status='sanity_failed'")
        print(f"sanity_failed → screen_failed: {r.rowcount} rows")

        # Backfill job_assessments with apply_verdict=Skip for newly-screened jobs that have no assessment
        r = con.execute("""
            INSERT INTO job_assessments (job_id, assessment_status, apply_verdict, assessed_at)
            SELECT id, 'screened', 'Skip', datetime('now')
            FROM jobs
            WHERE status = 'screened'
              AND id NOT IN (
                SELECT job_id FROM job_assessments WHERE apply_verdict IS NOT NULL
              )
            ON CONFLICT(job_id) DO UPDATE
              SET apply_verdict = 'Skip', assessment_status = 'screened'
              WHERE job_assessments.apply_verdict IS NULL
        """)
        print(f"Backfilled Skip assessment: {r.rowcount} rows")

        # Migrate old apply_verdict 'Apply' → 'Strong Apply' (research_job used to emit 'Apply')
        r = con.execute(
            "UPDATE job_assessments SET apply_verdict='Strong Apply' WHERE apply_verdict='Apply'"
        )
        print(f"apply_verdict 'Apply' → 'Strong Apply': {r.rowcount} rows")

        # Normalize casing: 'Apply with caution' → 'Apply with Caution'
        r = con.execute(
            "UPDATE job_assessments SET apply_verdict='Apply with Caution' WHERE apply_verdict='Apply with caution'"
        )
        print(f"apply_verdict casing fix: {r.rowcount} rows")

        con.commit()
        print("Migration complete.")
    finally:
        con.close()


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--db", default=DB_PATH)
    args = p.parse_args()
    migrate(args.db)
```

- [ ] **Step 2: Verify current status distribution before running**

```bash
sqlite3 jobs.db "SELECT status, COUNT(*) FROM jobs GROUP BY status ORDER BY COUNT(*) DESC"
```

Note the counts for `listed`, `skip`, `not_interested`, `sanity_failed`.

- [ ] **Step 3: Run migration**

```bash
python scripts/migrate_pipeline_statuses.py
```

Expected output: row counts for each migration step, `Migration complete.`

- [ ] **Step 4: Verify status distribution after**

```bash
sqlite3 jobs.db "SELECT status, COUNT(*) FROM jobs GROUP BY status ORDER BY COUNT(*) DESC"
```

`listed`, `skip`, `not_interested`, `sanity_failed` should all show 0 or be absent.

- [ ] **Step 5: Commit migration script**

```bash
git add scripts/migrate_pipeline_statuses.py
git commit -m "feat: add and run pipeline status migration script"
```

---

### Task 7: Drop unused `job_assessments` columns

> **Prerequisite:** Task 5 (research_job update) must be complete — `research_job.py` must no longer write these columns.

- [ ] **Step 1: Verify current schema**

```bash
sqlite3 jobs.db ".schema job_assessments"
```

Confirm columns `ic_or_management`, `visa_contract_structure`, `ai_native_assessment`, `assessment_notes`, `source_urls_json`, `raw_assessment_json` exist.

- [ ] **Step 2: Write column drop script**

Create `scripts/migrate_drop_assessment_columns.py`:

```python
#!/usr/bin/env python3
"""Drop unused columns from job_assessments. Run after research_job.py is updated."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from scripts.db import get_connection

DB_PATH = str(Path(__file__).parent.parent / "jobs.db")

COLUMNS_TO_DROP = [
    "ic_or_management",
    "visa_contract_structure",
    "ai_native_assessment",
    "assessment_notes",
    "source_urls_json",
    "raw_assessment_json",
]

def migrate(db_path: str = DB_PATH) -> None:
    con = get_connection(db_path)
    try:
        for col in COLUMNS_TO_DROP:
            try:
                con.execute(f"ALTER TABLE job_assessments DROP COLUMN {col}")
                print(f"Dropped: {col}")
            except Exception as e:
                print(f"Skipped {col}: {e}")
        con.commit()
        print("Column drop complete.")
    finally:
        con.close()

if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--db", default=DB_PATH)
    args = p.parse_args()
    migrate(args.db)
```

- [ ] **Step 3: Run column drop**

```bash
python scripts/migrate_drop_assessment_columns.py
```

Expected: 6 lines of `Dropped: <column>`, then `Column drop complete.`

- [ ] **Step 4: Verify schema**

```bash
sqlite3 jobs.db ".schema job_assessments"
```

Dropped columns should be absent.

- [ ] **Step 5: Commit**

```bash
git add scripts/migrate_drop_assessment_columns.py
git commit -m "feat: drop unused job_assessments columns (ic_or_management, visa_contract_structure, etc.)"
```

---

## Chunk 4: Dashboard

### Task 8: Update `dashboard/lib/db.ts`

**Files:**
- Modify: `dashboard/lib/db.ts`

- [ ] **Step 1: Update `JobAssessment` type**

Remove fields: `ic_or_management`, `visa_contract_structure`, `ai_native_assessment`, `assessment_notes`, `source_urls_json`, `raw_assessment_json`.

Updated type:
```typescript
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
```

- [ ] **Step 2: Update `listJobs` filter**

In `listJobs()`, find the conditions array initialization:
```typescript
const conditions: string[] = ["j.deleted_at IS NULL", "j.status != 'skip'"];
```

Change to:
```typescript
const conditions: string[] = [
  "j.deleted_at IS NULL",
  "(ja.apply_verdict != 'Skip' OR ja.apply_verdict IS NULL)",
];
```

- [ ] **Step 3: Build check**

```bash
cd /Users/zall/interviews/dashboard && npx tsc --noEmit 2>&1 | head -30
```

Fix any type errors.

- [ ] **Step 4: Commit**

```bash
git add dashboard/lib/db.ts
git commit -m "refactor: update db.ts types and listJobs filter for new status/verdict schema"
```

---

### Task 9: Update `dashboard/app/components/JobDetail.tsx`

**Files:**
- Modify: `dashboard/app/components/JobDetail.tsx`

- [ ] **Step 1: Update `STATUSES` array and handle pipeline status display**

Current:
```typescript
const STATUSES = ["new","interesting","not_interested","researching","researched","draft_ready","applied","interviewing","rejected","archived"];
```

New — split pipeline stages from manual workflow statuses:
```typescript
// Pipeline stages set by code — read-only, never in the editable dropdown
const PIPELINE_STATUSES = new Set(["new","enriched","screened","researching","researched","enrich_failed","screen_failed"]);
// Manual workflow statuses — user can set these via the dropdown
const STATUSES = ["interesting","draft_ready","applied","interviewing","rejected","archived"];
```

The status `<select>` dropdown must only offer `STATUSES` options. However, when the current job status is a pipeline status (e.g. `"screened"`), the dropdown will show blank because `"screened"` has no `<option>`. Fix: display the current pipeline status as a read-only badge/label above the dropdown, and initialize the dropdown to empty / `""` when the current status is a pipeline status. The user picks a manual status to override it. Add a placeholder `<option value="">— pipeline stage —</option>` as the default when no manual status is set.

- [ ] **Step 2: Update `STATUS_ACCENT` map**

Add missing entries, remove obsolete ones:
```typescript
const STATUS_ACCENT: Record<string, string> = {
  new:           "#94a3b8",
  enriched:      "#60a5fa",
  screened:      "#34d399",
  researching:   "#fbbf24",
  researched:    "#c084fc",
  enrich_failed: "#ef4444",
  screen_failed: "#f97316",
  // manual workflow statuses
  interesting:   "#4ade80",
  draft_ready:   "#fb923c",
  applied:       "#818cf8",
  interviewing:  "#2dd4bf",
  rejected:      "#f87171",
  archived:      "#475569",
};
```

- [ ] **Step 3: Update `STATUS_LABELS` map**

```typescript
const STATUS_LABELS: Record<string, string> = {
  new:           "New",
  enriched:      "Enriched",
  screened:      "Screened",
  researching:   "Researching…",
  researched:    "Researched",
  enrich_failed: "Enrich Failed",
  screen_failed: "Screen Failed",
  interesting:   "Interesting",
  draft_ready:   "Draft Ready",
  applied:       "Applied",
  interviewing:  "Interviewing",
  rejected:      "Rejected",
  archived:      "Archived",
};
```

- [ ] **Step 4: Update `VERDICT_CONFIG`**

Replace the entire `VERDICT_CONFIG` and `DEFAULT_VERDICT`:
```typescript
const VERDICT_CONFIG: Record<string, { bg: string; accent: string; label: string; labelColor: string }> = {
  "Strong Apply":       { bg: "var(--green-bg)",  accent: "var(--green)",        label: "STRONG APPLY",       labelColor: "var(--green)" },
  "Apply with Caution": { bg: "var(--amber-bg)",  accent: "var(--amber)",        label: "APPLY WITH CAUTION", labelColor: "var(--amber)" },
  "Need Research":      { bg: "rgba(96,165,250,0.10)", accent: "#60a5fa",        label: "NEED RESEARCH",      labelColor: "#60a5fa" },
  "Skip":               { bg: "var(--red-bg)",    accent: "var(--red-border)",   label: "SKIP",               labelColor: "var(--text-2)" },
};
const DEFAULT_VERDICT = { bg: "var(--surface)", accent: "var(--border-hi)", label: "NOT SCREENED", labelColor: "var(--text-3)" };
```

- [ ] **Step 5: Update `canApply` check**

Find the `canApply` variable (currently checks for `"Apply"` and `"Apply with caution"`). Update:
```typescript
const canApply = assessment?.apply_verdict === "Strong Apply" || assessment?.apply_verdict === "Apply with Caution";
```

- [ ] **Step 6: Remove dropped-column JSX render sections**

Search `JobDetail.tsx` for any JSX that renders `assessment?.assessment_notes`, `assessment?.ai_native_assessment`, `assessment?.ic_or_management`, `assessment?.visa_contract_structure`. Delete those render blocks — these fields no longer exist in the `JobAssessment` type after Task 8. The TypeScript build will catch any remaining references.

```bash
grep -n "assessment_notes\|ai_native_assessment\|ic_or_management\|visa_contract_structure" dashboard/app/components/JobDetail.tsx
```

Delete each matching JSX block.

- [ ] **Step 7: Update Research button visibility**

Find where the Research button is conditionally shown. Change the condition to:
```typescript
(job.status === "screened" || job.status === "researched")
```

- [ ] **Step 8: Build check**

```bash
cd /Users/zall/interviews/dashboard && npx tsc --noEmit 2>&1 | head -30
```

Fix any type errors.

- [ ] **Step 9: Commit**

```bash
git add dashboard/app/components/JobDetail.tsx
git commit -m "feat: update JobDetail for new status/verdict schema — VERDICT_CONFIG, STATUS_LABELS, canApply"
```

---

### Task 10: Update `JobList` — apply_verdict filter + relevance score

**Files:**
- Modify: `dashboard/app/components/JobList.tsx` (or wherever filter UI lives)
- Modify: `dashboard/lib/db.ts` `JobFilters` type if needed

- [ ] **Step 1: Check current filter UI**

```bash
grep -n "filter\|verdict\|relevance" dashboard/app/components/JobList.tsx | head -30
```

- [ ] **Step 2: Add `apply_verdict` to `JobFilters` type in `db.ts`**

```typescript
export type JobFilters = {
  status?: string;
  provider?: string;
  country?: string;
  remote_scope?: string;
  unresearched?: boolean;
  new_only?: boolean;
  apply_verdict?: string;   // add this
};
```

And handle in `listJobs`:
```typescript
if (filters.apply_verdict) { conditions.push("ja.apply_verdict = ?"); params.push(filters.apply_verdict); }
```

- [ ] **Step 3: Add verdict filter to job list UI**

In `JobList.tsx`, add a filter button/dropdown for `apply_verdict` values: All, Strong Apply, Apply with Caution, Need Research (hide Skip by default).

The exact implementation depends on how current filters are structured — follow the existing filter pattern.

- [ ] **Step 4: Show `relevance_score` in job list row**

Find where job rows are rendered. Add `relevance_score` display (e.g., a small badge `R:85`) next to the company/title. Follow existing styling patterns.

- [ ] **Step 5: Build and verify no TS errors**

```bash
cd /Users/zall/interviews/dashboard && npx tsc --noEmit 2>&1 | head -30
```

- [ ] **Step 6: Commit**

```bash
git add dashboard/app/components/JobList.tsx dashboard/lib/db.ts
git commit -m "feat: add apply_verdict filter and relevance_score to job list"
```

---

## Chunk 5: Cleanup

### Task 11: Delete old files + update old tests

**Files:**
- Delete: `skills/sanity-check-job/SKILL.md` (and dir)
- Delete or archive: `scripts/pipeline/sanity_check_job.py`
- Update: `tests/pipeline/test_sanity_check_job.py` → rename to `test_screen_job.py` (already created in Task 2; delete the old file)

- [ ] **Step 1: Delete old sanity-check files**

```bash
rm -rf skills/sanity-check-job/
rm scripts/pipeline/sanity_check_job.py
rm tests/pipeline/test_sanity_check_job.py
```

- [ ] **Step 2: Run full test suite**

```bash
cd /Users/zall/interviews && python -m pytest tests/ -v --tb=short 2>&1 | tail -40
```

Fix any remaining import errors or broken references to `sanity_check_job`.

- [ ] **Step 3: Final build check**

```bash
cd /Users/zall/interviews/dashboard && npx tsc --noEmit && echo "TS OK"
```

- [ ] **Step 4: Final commit**

```bash
git add -A
git commit -m "chore: remove sanity_check_job files, final cleanup after pipeline redesign"
```

---

## Manual Smoke Test

After all tasks complete:

1. Start dashboard: `cd dashboard && npm run dev`
2. Open job list — verify Skip jobs are hidden by default
3. Open a job detail with `status='screened'` — verify assessment fields visible, Research button present
4. Open a job detail with `status='researched'` — verify `strong_apply`/`apply_with_caution` renders correctly in VERDICT_CONFIG
5. Run pipeline manually on one job: `python scripts/scraping_pipeline.py --provider greenhouse` (or dry-run with a single known job)
6. Verify the job goes `new → enriched → screened` and `job_assessments` row is created
