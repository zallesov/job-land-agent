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

`jobs.status` becomes a linear pipeline indicator:

| Status | Set by | Meaning |
|---|---|---|
| `new` | `ingest_jobs` | Job scraped and inserted |
| `enriched` | `enrich_job` | Description/metadata fetched |
| `screened` | `screen_job` | Lightweight assessment complete |
| `researching` | `research_job` runner | Manual research in progress |
| `researched` | `research_job` | Full research complete |
| `enrich_failed` | `enrich_job` | Enrichment error |
| `screen_failed` | `screen_job` | Screening error |

**Removed:** `listed`, `not_interested`, `sanity_failed` — these concepts move to `apply_verdict`.

`jobs.current_interview_status` — unchanged, manual UI only, not part of pipeline.

### 2. `job_assessments` Schema

Schema is trimmed. Fields removed: `ic_or_management`, `visa_contract_structure`, `ai_native_assessment`, `assessment_notes`, `source_urls_json`, `raw_assessment_json`, `raw_research_json`.

| Field | Set by | Notes |
|---|---|---|
| `relevance_score` | screen_job | 0–100 |
| `apply_verdict` | screen_job; research may overwrite | `Strong Apply` / `Apply with Caution` / `Need Research` / `Skip` |
| `one_line_summary` | screen_job | |
| `seniority_fit` | screen_job | |
| `tech_stack_fit` | screen_job | |
| `remote_eligibility` | screen_job | |
| `salary_assessment` | screen_job; research refines | screen uses posted salary; research finds actual range |
| `red_flag_scan` | research only | glassdoor signals, risk news |
| `assessment_status` | both | `screened` / `researched` |

`company_research` table — unchanged, populated only by manual research.

### 3. `screen_job` Step

**Replaces:** `sanity_check_job.py`  
**File:** `scripts/pipeline/screen_job.py`  
**Hermes skill:** `skills/screen-job/` (new, replaces `skills/sanity-check-job/`)

The skill receives: job title, description, company name, location, remote_scope, salary_range (if available). It returns:

```json
{
  "apply_verdict": "Need Research | Strong Apply | Apply with Caution | Skip",
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

### 4. `research_job` Step (Manual Only)

**No logic changes.** Changes:
- Removed from `scraping_pipeline.py` (no more `_queue_research()`)
- Triggered only via UI button → `createResearchCommand` → `agent_commands` row → async runner
- On completion: overwrites `apply_verdict`, refines `salary_assessment`, adds `red_flag_scan` in `job_assessments`; populates `company_research` table
- Status transitions: `screened → researching → researched`

### 5. Pipeline Orchestration

**`scripts/scraping_pipeline.py`** simplified:

```
scrape → dedup → ingest (status: new)
                      → enrich_job (status: enriched | enrich_failed)
                              → screen_job (status: screened | screen_failed)
```

Removed from pipeline: `_queue_research()`, `send_daily_digest` (or kept separately if needed).

### 6. UI Changes

**Job list:**
- Filter by `apply_verdict` replaces some status filters
- Default view hides jobs where `apply_verdict = 'Skip'`
- `relevance_score` visible in list row

**Job detail header:**
- `status` shown as pipeline stage badge
- `apply_verdict` shown as separate colored tag
- Research button visible for `screened` and `researched` jobs only

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

---

## Migration

1. DB migration: rename `listed` → `new`, `not_interested` → `screened` (with apply_verdict='Skip' backfill), `sanity_failed` → `screen_failed`, drop unused `job_assessments` columns
2. Python: rename `sanity_check_job.py` → `screen_job.py`, update `scraping_pipeline.py`
3. Hermes skill: create `skills/screen-job/` with new prompt, remove `skills/sanity-check-job/`
4. Dashboard: update `db.ts` types, status filters, job detail UI

## Out of Scope

- Changing research_job LLM prompt or company_research schema
- Interview stage workflow (manual UI only, no pipeline changes)
- Telegram notifications redesign
