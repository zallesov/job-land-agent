---
name: enrich-job
description: Use when enriching JobLand job records through JobLandMCP or diagnosing enrichment state.
---

# Enrich Job

## Hard Rule

Use JobLandMCP only. Do not run local enrichment scripts, direct backend clients, SQL, or ad-hoc write snippets.

## Workflow

1. Read the job with `jobs_get` or locate it with `jobs_find_by_url` / `jobs_search`.
2. If a JobLandMCP enrichment tool is available, call it for the target job id or URL.
3. Re-read the job with `jobs_get` and verify title, company, description, apply URL, salary, location, and status fields returned by MCP.
4. If no enrichment MCP tool exists, report that enrichment is not exposed through JobLandMCP and stop.

## Manual Corrections

Only use `jobs_update` when the user explicitly asks to write corrected fields. Keep updates limited to fields visible in MCP responses. Do not mention or rely on backend storage internals.

## Browser Visibility

If an MCP-backed enrichment operation opens Chrome, it must use the visible authenticated browser session so the user can watch provider interactions. If the browser is unavailable, ask the user to start it or log in through the visible browser.
