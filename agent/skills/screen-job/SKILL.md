---
name: screen-job
description: Use when screening a JobLand job against the candidate profile or reviewing an existing assessment.
---

# Screen Job

## Hard Rule

Use JobLandMCP for job reads and writes. Do not use local screening scripts, SQL, direct backend clients, or ad-hoc snippets.

## Workflow

1. Read the job with `jobs_get`.
2. If a JobLandMCP screening tool exists, call it for the job id and then re-read the job/assessment state.
3. If no screening MCP tool exists, perform a read-only assessment in the response and do not write it.
4. Use `jobs_update` only if the user explicitly asks to persist a field and the MCP schema exposes that field.

## Assessment Rules

Return a JSON assessment with:
- `apply_verdict`: `Strong Apply`, `Apply with Caution`, `Need Research`, or `Skip`
- `relevance_score`: integer 0-100
- `one_line_summary`
- `seniority_fit`
- `tech_stack_fit`
- `remote_eligibility`
- `salary_assessment`

Use the job description and candidate profile only. Do not research the company in this skill.

If description is missing or too short, use `Need Research`.
