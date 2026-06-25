---
name: add-job-by-url
description: Use when adding or tracking a single job posting URL through JobLandMCP.
---

# Add Job by URL

## Hard Rule

Use JobLandMCP only. Do not run local add-job scripts, direct backend clients, SQL, helper snippets, or manual storage writes.

## Workflow

1. Use `jobs_find_by_url` with the exact URL.
2. If a record exists, report that it is already tracked and include the id, title, company, and status fields returned by MCP.
3. If no record exists and a JobLandMCP add/import tool is available, call it with the URL.
4. If no add/import tool exists, ask for approval to create a minimal record with `jobs_create`.
5. After creation, use only JobLandMCP enrichment/screening tools if they exist. If they do not exist, report the missing MCP capability.

## Minimal Create Fields

When the user approves a minimal `jobs_create`, include only fields that can be derived directly from the URL or user-provided text. Do not invent company names, descriptions, salaries, or statuses.

## Failure Handling

- Duplicate: stop after reporting the existing record.
- Enrichment unavailable: report that JobLandMCP lacks enrichment capability.
- Screening unavailable: report that JobLandMCP lacks screening capability.
- Any write failure: report the MCP error and stop.
