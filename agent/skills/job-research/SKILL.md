---
name: job-research
description: Use when researching a JobLand job/company and saving or reviewing research through JobLandMCP.
---

# Job Research

## Hard Rule

Use JobLandMCP only for JobLand records. Do not use local research scripts, direct backend clients, SQL, database files, or storage-specific knowledge.

## Input

Prompts may include `job_id=<ID>` and optionally `command_id=<ID>`. Treat ids as opaque JobLand record ids.

## Workflow

1. Read the job with `jobs_get`.
2. If a command record or research job state is exposed by JobLandMCP, mark it using MCP only.
3. Perform web research using normal browsing/search tools:
   - original job posting URL
   - company website
   - LinkedIn company page
   - Glassdoor or similar review sources
   - funding/news sources where relevant
4. Produce structured research fields.
5. Persist results only through a JobLandMCP research/assessment tool if available. If only generic `jobs_update` is available, write only fields the user explicitly approved and the tool schema clearly supports.
6. If no MCP write path exists for research, return the structured result and state that persistence requires a JobLandMCP research-write capability.

## Fast Fit Check

Before deep company research, read the job title and description. Fast-exit as `Skip` when clear hard disqualifiers appear:
- junior, intern, trainee, new graduate, or clearly below target seniority
- non-engineering role
- relocation/on-site constraint outside the user's target geography
- language, salary, or domain conflict with the candidate profile

## Output Shape

Return structured research with:
- `legitimacy_check`
- `hiring_entity_type`
- `founded_year`
- `hq_location`
- `employee_count`
- `funding_summary`
- `risk_news`
- `glassdoor_summary`
- `trustworthiness_score`
- `relevance_score`
- `apply_verdict`
- `one_line_summary`
- `red_flag_scan`
- `seniority_fit`
- `tech_stack_fit`
- `salary_range`
- `salary_assessment`
- `remote_eligibility`
- `research_notes`
- `apply_url`
- `source_urls`

Do not mention or infer the storage backend.
