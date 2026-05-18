# Plan 1: SQLite Canonical Store

## Summary

Create a fresh `jobs.db` as the canonical operational store for the autonomous job pipeline. Do not import existing `jobs_all.xlsx` in v1; keep current XLSX files as legacy reference. Provider scrapers will populate SQLite through future ingestion runs.

Use a hybrid schema: typed columns for fields used in filtering, sorting, joins, and workflow; JSON/text fields for provider-specific payloads, long research notes, command results, and source evidence.

## Schema

Create these tables:

- `jobs`
  - `id`, `url UNIQUE`, `provider`, `provider_job_id`
  - `company_id`, `posted_company_name`, `actual_hiring_company_id`
  - `title`, `description`, `apply_url`
  - `location`, `country`, `remote_scope`
  - `date_posted`, `first_seen`, `last_seen`
  - `status`, `comment`, `current_interview_status`
  - `source_payload_json`
  - `created_at`, `updated_at`
- `companies`
  - `id`, `display_name`, `normalized_name`
  - `website_url`, `domain`
  - `linkedin_url`, `glassdoor_url`, `crunchbase_url`
  - `created_at`, `updated_at`
  - unique identity: prefer `domain`; fall back to `normalized_name`
- `company_research`
  - `id`, `company_id`
  - `researched_at`, `research_status`
  - `legitimacy_check`, `hiring_entity_type`
  - `founded_year`, `hq_location`, `employee_count`, `headcount_trend`
  - `funding_summary`, `funding_stage`, `risk_news`
  - `glassdoor_summary`, `trustworthiness_score`
  - `research_notes`, `source_urls_json`
  - `raw_research_json`
- `job_assessments`
  - `id`, `job_id UNIQUE`
  - `assessed_at`, `assessment_status`
  - `relevance_score`, `apply_verdict`, `one_line_summary`
  - `red_flag_scan`, `seniority_fit`, `tech_stack_fit`, `ic_or_management`
  - `salary_assessment`, `remote_eligibility`, `visa_contract_structure`, `ai_native_assessment`
  - `assessment_notes`, `source_urls_json`
  - `raw_assessment_json`
- `applications`
  - `id`, `job_id`
  - `status`
  - `tailored_cv_path`, `cover_letter_path`, `application_notes_path`
  - `created_at`, `submitted_at`, `updated_at`
  - `error`
- `agent_commands`
  - `id`, `command_type`, `payload_json`
  - `status`
  - `created_by`
  - `created_at`, `started_at`, `finished_at`
  - `result_json`, `error`
- `pipeline_runs`
  - `id`, `run_type`, `status`
  - `started_at`, `finished_at`
  - `summary_json`, `error`
- `events`
  - `id`, `entity_type`, `entity_id`
  - `event_type`, `actor`
  - `event_json`
  - `created_at`

## Status Values

Use controlled enums in application logic:

- `jobs.status`: `new`, `interesting`, `not_interested`, `researching`, `researched`, `draft_ready`, `applied`, `interviewing`, `rejected`, `archived`
- `job_assessments.assessment_status`: `pending`, `researched`, `failed`, `stale`
- `company_research.research_status`: `pending`, `researched`, `failed`, `stale`
- `applications.status`: `draft_requested`, `draft_ready`, `submitted`, `failed`, `cancelled`
- `agent_commands.status`: `pending`, `running`, `succeeded`, `failed`, `cancelled`
- `pipeline_runs.status`: `running`, `succeeded`, `failed`, `partial`

Free-text nuance remains in `comment`, `current_interview_status`, notes fields, and JSON payloads.

## Identity And Dedupe Rules

- Jobs dedupe strictly by `url`.
- Companies dedupe by `domain` when known.
- If no domain is known, dedupe by `normalized_name`.
- Preserve both `posted_company_name` and `actual_hiring_company_id`.
- Recruiter posts can have the recruiter as `company_id` and the real employer as `actual_hiring_company_id` only if discovered.
- Company research cache is keyed by `company_id`, so multiple jobs from the same company reuse research.

## Implementation Notes

- Create a small DB module used by ingestion, research, Hermes workers, and Next.js server code.
- Enable SQLite foreign keys.
- Add indexes on `jobs.url`, `jobs.status`, `jobs.provider`, `jobs.country`, `jobs.company_id`, `companies.domain`, `companies.normalized_name`, `agent_commands.status`, and `pipeline_runs.started_at`.
- Do not add SQLite full-text search in v1.
- Do not import current `jobs_all.xlsx` in v1.
- Keep XLSX/CSV as legacy exports or debug artifacts only.

## Test Plan

- Create DB from scratch and verify all tables/indexes exist.
- Insert the same job URL twice and verify only one canonical job exists.
- Insert two jobs for the same company domain and verify one shared company record.
- Insert a recruiter-posted job and verify posted company and actual hiring company can differ.
- Insert and update job statuses without changing comments.
- Insert an `agent_commands` row and move it through `pending -> running -> succeeded`.
- Insert an event for a job status change and verify the current job row plus event log both reflect the change.

## Assumptions

- SQLite starts fresh for v1.
- Existing XLSX workbooks are not migrated initially.
- SQLite is the only canonical state once the new pipeline is active.
- Provider scrapers do not write directly to arbitrary tables; ingestion owns job/company upserts.
- Next.js and Hermes both access SQLite through shared repository functions or scripts, not ad hoc SQL scattered through the codebase.
