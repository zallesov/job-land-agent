# Pipeline & Status Redesign

**Date:** 2026-05-22  
**Status:** Draft

## Problem

The current pipeline auto-queues expensive LLM research for every new job. Sanity check only produces a binary pass/skip verdict with no structured assessment data. Status values are inconsistent and don't map cleanly to pipeline stages. The result: wasted API calls, no lightweight triage, and confusing job states in the UI.

## Goals

1. Move lightweight job assessment (without internet/company research) to the `screen_job` pipeline step
2. Remove auto-research from the pipeline — research is manual only
3. Simplify `jobs.status` to map 1:1 with pipeline stages
4. Separate pipeline state (`status`) from job verdict (`apply_verdict`)

---

## Design

### 1. Status Values

`jobs.status` becomes a linear pipeline indicator only. **Manual workflow states** (`applied`, `interviewing`, `rejected`, `archived`, `draft_ready`, `interesting`) are preserved as valid `jobs.status` values set only via the UI — they are never written by the pipeline. The pipeline only writes the pipeline-stage statuses listed below.

| Status | Set by | Meaning |
|---|---|---|
| `new` | `ingest_jobs` | Job scraped and inserted |
| `enriched` | `enrich_job` | Description/metadata fetched |
| `screened` | `screen_job` | Lightweight assessment complete |
| `researching` | `research_job.py` at start | Manual research in progress |
| `researched` | `research_job.py` on success | Full research complete |
| `enrich_failed` | `enrich_job` | Enrichment error |
| `screen_failed` | `screen_job` | Screening error |

**Pipeline-removed statuses (migrate away):** `listed`, `not_interested`, `sanity_failed`, `skip` — see Migration section.

**Preserved manual statuses (UI only):** `interesting`, `draft_ready`, `applied`, `interviewing`, `rejected`, `archived` — no pipeline code touches these.

`jobs.current_interview_status` — unchanged, manual UI only, not part of pipeline.

### 2. `apply_verdict` Enum

Shared by both `screen_job` and `research_job`. Full enum:

| Value | Meaning | Who sets it |
|---|---|---|
| `Strong Apply` | Clearly a good fit | screen_job or research_job |
| `Apply with Caution` | Worth applying but caveats exist | screen_job or research_job |
| `Need Research` | Interesting but can't assess without company data | screen_job only |
| `Skip` | Not a fit | screen_job or research_job |

`research_job` always overwrites `apply_verdict` — after research runs, `Need Research` is replaced by a definitive verdict. `research_job.py` must be updated to produce `Strong Apply` / `Apply with Caution` / `Skip` (not the current `Apply`).

### 3. `job_assessments` Schema

Schema is trimmed. Fields removed: `ic_or_management`, `visa_contract_structure`, `ai_native_assessment`, `assessment_notes`, `source_urls_json`, `raw_assessment_json`.

**Note:** columns are dropped only after `research_job.py` is updated to stop writing them (see Migration sequencing).

| Field | Set by | Notes |
|---|---|---|
| `relevance_score` | screen_job | 0–100 |
| `apply_verdict` | screen_job; research overwrites | see enum above |
| `one_line_summary` | screen_job | |
| `seniority_fit` | screen_job | |
| `tech_stack_fit` | screen_job | |
| `remote_eligibility` | screen_job | |
| `salary_assessment` | screen_job; research refines | screen uses posted salary; research finds actual range |
| `red_flag_scan` | research only | glassdoor signals, risk news |
| `assessment_status` | both | `screened` / `researched` |

`company_research` table — unchanged, populated only by manual research.

### 4. `screen_job` Step

**Replaces:** `sanity_check_job.py`  
**File:** `scripts/pipeline/screen_job.py`  
**Hermes skill:** `skills/screen-job/` (new, replaces `skills/sanity-check-job/`)

The skill receives: job title, description, company name, location, remote_scope, salary_range (if available). It returns:

```json
{
  "apply_verdict": "Strong Apply | Apply with Caution | Need Research | Skip",
  "relevance_score": 72,
  "one_line_summary": "...",
  "seniority_fit": "Senior IC role, matches target level",
  "tech_stack_fit": "Python/React match, no Rust required",
  "remote_eligibility": "Remote OK for EU timezone",
  "salary_assessment": "~$120k estimated, no explicit range"
}
```

**DB writes:**
- Upserts `job_assessments` row with `assessment_status = 'screened'`
- Sets `jobs.status = 'screened'`
- On failure: sets `jobs.status = 'screen_failed'`, writes error to `jobs.comment`

All jobs reach `screened` regardless of verdict — verdict goes to `apply_verdict`, not status.

### 5. `research_job` Step (Manual Only)

**Changes from current:**
- Removed from `scraping_pipeline.py` (no more `_queue_research()`)
- Triggered only via UI button → `createResearchCommand` → `agent_commands` row → async runner
- `research_job.py` sets `jobs.status = 'researching'` at the start of processing (before LLM call), then `'researched'` on success
- Updates `apply_verdict` to one of `Strong Apply / Apply with Caution / Skip` (removing `Need Research`)
- Refines `salary_assessment`, adds `red_flag_scan` in `job_assessments`
- Populates `company_research` table
- Updated to produce `Strong Apply` in addition to `Apply with Caution` / `Skip`

### 6. Pipeline Orchestration

**`scripts/scraping_pipeline.py`** simplified:

```
scrape → dedup → ingest (status: new)
                      → enrich_job (status: enriched | enrich_failed)
                              → screen_job (status: screened | screen_failed)
```

Removed from pipeline: `_queue_research()`.

`notify.py`: rename parameter `sanity_failures` → `screen_failures` and update message text.

### 7. UI Changes

**Job list:**
- Filter by `apply_verdict` replaces some status filters
- Default view hides jobs where `apply_verdict = 'Skip'`
- `relevance_score` visible in list row

**Verdict display colors:**

| apply_verdict | Color |
|---|---|
| `Strong Apply` | green |
| `Apply with Caution` | yellow |
| `Need Research` | blue |
| `Skip` | gray |

**Job detail header:**
- `status` shown as pipeline stage badge
- `apply_verdict` shown as separate colored tag
- Research button visible for jobs with `jobs.status IN ('screened', 'researched')`

**Status display mapping:**

| DB value | UI label |
|---|---|
| `new` | New |
| `enriched` | Enriched |
| `screened` | Screened |
| `researching` | Researching… |
| `researched` | Researched |
| `enrich_failed` | ⚠ Enrich failed |
| `screen_failed` | ⚠ Screen failed |
| `interesting` | Interesting (manual) |
| `draft_ready` | Draft ready (manual) |
| `applied` | Applied (manual) |
| `interviewing` | Interviewing (manual) |
| `rejected` | Rejected (manual) |
| `archived` | Archived (manual) |

---

## Migration

**Sequencing constraint:** update `research_job.py` to stop writing dropped columns BEFORE running the DB column-drop migration.

### Step 1 — DB status migration

```sql
-- listed → new (post-ingest jobs that were never enriched)
UPDATE jobs SET status = 'new' WHERE status = 'listed';

-- skip and not_interested → screened with apply_verdict=Skip
UPDATE jobs SET status = 'screened' WHERE status IN ('skip', 'not_interested');

-- backfill job_assessments for newly-screened rows that have no assessment yet
-- Note: ON CONFLICT leaves existing assessments (e.g. already-researched jobs) untouched
INSERT INTO job_assessments (job_id, assessment_status, apply_verdict)
  SELECT id, 'screened', 'Skip' FROM jobs
  WHERE status = 'screened'
    AND id NOT IN (SELECT job_id FROM job_assessments WHERE apply_verdict IS NOT NULL)
  ON CONFLICT(job_id) DO UPDATE
    SET apply_verdict = 'Skip', assessment_status = 'screened'
    WHERE excluded.apply_verdict IS NULL;

-- sanity_failed → screen_failed
UPDATE jobs SET status = 'screen_failed' WHERE status = 'sanity_failed';
```

### Step 2 — Code updates (before column drop)

1. Update `research_job.py`:
   - Add `jobs.status = 'researching'` write before the LLM call (new `con.execute` block)
   - Change `apply_verdict` SCHEMA_DESCRIPTION to: `"Strong Apply" | "Apply with Caution" | "Skip"` (remove `Apply`, add `Strong Apply`)
   - Stop writing dropped columns (`ic_or_management`, `visa_contract_structure`, `ai_native_assessment`, `assessment_notes`, `source_urls_json`, `raw_assessment_json`)
2. Rename `scripts/pipeline/sanity_check_job.py` → `scripts/pipeline/screen_job.py`
3. Update `scripts/scraping_pipeline.py`: use `screen_job`, remove `_queue_research`, rename `sanity_failures` → `screen_failures`
4. Update `scripts/pipeline/notify.py`: rename parameter `sanity_failures` → `screen_failures`
5. Create `skills/screen-job/` with new prompt; remove `skills/sanity-check-job/`

### Step 3 — DB column drop

```sql
ALTER TABLE job_assessments DROP COLUMN ic_or_management;
ALTER TABLE job_assessments DROP COLUMN visa_contract_structure;
ALTER TABLE job_assessments DROP COLUMN ai_native_assessment;
ALTER TABLE job_assessments DROP COLUMN assessment_notes;
ALTER TABLE job_assessments DROP COLUMN source_urls_json;
ALTER TABLE job_assessments DROP COLUMN raw_assessment_json;
```

### Step 4 — Dashboard

1. `dashboard/lib/db.ts`:
   - Update `Job` type `status` field enum
   - Update `JobAssessment` type `apply_verdict` to new enum values
   - In `listJobs`: replace `j.status != 'skip'` condition with `(ja.apply_verdict != 'Skip' OR ja.apply_verdict IS NULL)` — filtering is now on verdict, not status

2. `dashboard/app/components/JobDetail.tsx`:
   - Update `STATUSES` array: remove `not_interested`; keep manual-only statuses; pipeline statuses (`new`, `enriched`, `screened`, `researching`, `researched`, `enrich_failed`, `screen_failed`) should either be hidden from the manual dropdown or shown as read-only
   - Update `STATUS_LABELS` and `STATUS_ACCENT` maps: add entries for `enriched`, `screened`, `screen_failed`; remove `sanity_failed`, `not_interested`
   - Update `VERDICT_CONFIG`: add `"Strong Apply"` (green) and `"Need Research"` (blue) entries; remove legacy `"Apply"` entry; update `"Apply with caution"` key to `"Apply with Caution"` (capital C)
   - Update `canApply` condition: `assessment?.apply_verdict === "Strong Apply" || assessment?.apply_verdict === "Apply with Caution"`
   - Research button: show when `job.status` is `'screened'` or `'researched'`

3. Update job list component: add `apply_verdict` filter UI, default hide `Skip` jobs, show `relevance_score` in row

---

## Out of Scope

- Changing `company_research` schema
- Interview stage workflow (manual UI only, no pipeline changes)
- Telegram notifications redesign
