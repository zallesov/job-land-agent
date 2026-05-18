# Plan 5: Research Worker

## Summary

Implement a reusable `research_job` worker that Hermes can run from a Next.js-triggered command. V1 supports researching one job at a time. The worker reads the job from SQLite, reuses existing company research forever unless a future force-refresh command is added, performs job-specific due diligence, writes structured company/job assessment records, and updates command status.

The current spreadsheet-based due diligence skill becomes the research brief and scoring source, but the production worker writes to SQLite instead of XLSX.

## Key Changes

### Worker Contract

Add one stable command:

```bash
python scripts/research_job.py --db jobs.db --job-id 123
```

The worker must:

- validate the job exists
- load job, company, posting URL, apply URL, description, and source payload
- reuse existing `company_research` for `company_id` if present
- research the company only if no research exists
- always perform job-specific assessment for the selected job
- write `company_research` and `job_assessments`
- update `jobs.status` to `researched` only when assessment succeeds
- write `events` rows for research start/success/failure
- exit nonzero only for hard failures: DB errors, invalid input, unavailable required runtime, or invalid structured output

### Research Engine

Use a deterministic script that calls configured web/search and LLM APIs. Hermes and Next.js never depend on an interactive Codex session for production research.

The script produces structured JSON internally, then maps it to SQLite columns:

- company-level facts into `company_research`
- job-specific fit/verdict into `job_assessments`
- source URLs into `source_urls_json`
- full structured model output into `raw_research_json` / `raw_assessment_json`

The script must follow the existing due diligence brief:

- legitimacy check
- hiring entity type and mismatch
- company profile
- funding/stage/news
- Glassdoor/reputation
- red flags
- seniority/tech/remote/salary/visa fit
- AI-native assessment
- one-line verdict
- relevance score
- company trustworthiness score

### Source And Evidence Policy

Use best-effort required sources:

- original job posting or apply URL
- company website
- LinkedIn company profile
- Glassdoor or similar
- Crunchbase or funding source
- credible news search

If a source cannot be found or accessed, write `Not found`; do not guess. Cite a source URL for every non-obvious claim.

Store only:

- concise notes
- source URLs
- structured JSON outputs

Do not archive full pages or long source excerpts.

### Company Cache And Recruiters

Company research is reused forever by default. The dashboard should show `researched_at` so stale data is visible. A future `refresh_company_research` command can override this.

For recruiter/agency postings:

- research the named posting entity
- flag `hiring_entity_type` as recruiter/agency/intermediary
- set actual hiring company to `Not found` unless explicitly discovered
- do not infer the hidden client
- lower trust score appropriately and prefer `Apply with caution` when role fit is otherwise strong

### Failure And Status Behavior

Partial research is acceptable:

- missing Glassdoor, Crunchbase, LinkedIn, salary, or funding does not fail the command
- unavailable facts are written as `Not found`
- the assessment can still be `researched` if the worker produced a coherent cited result

Hard failures mark:

- `job_assessments.assessment_status = failed` if a job assessment row exists
- `agent_commands.status = failed`
- `agent_commands.error`
- an `events` row with failure details

## Test Plan

- Research a valid job with no company research and verify both `company_research` and `job_assessments` are created.
- Research a second job for the same company and verify company research is reused.
- Research a recruiter-posted job and verify mismatch/intermediary handling without inferring the client.
- Simulate missing Glassdoor/Crunchbase and verify fields say `Not found` while command succeeds.
- Simulate invalid job id and verify command fails cleanly.
- Simulate malformed LLM output and verify command fails without corrupting existing records.
- Verify every non-obvious claim field includes source URLs in either notes or `source_urls_json`.
- Verify manual fields `comment` and `current_interview_status` are not modified.

## Assumptions

- V1 supports `research_job` only; batch research will later call this command repeatedly.
- Company research cache is reused forever unless a future explicit refresh command is added.
- Research is dashboard-triggered, not part of the daily Hermes pipeline in v1.
- Production research runs through scripts and APIs, not interactive Codex sessions.
- The existing due diligence skill remains the source prompt/spec for research content and scoring.
