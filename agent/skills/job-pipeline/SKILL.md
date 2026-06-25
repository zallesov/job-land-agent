---
name: job-pipeline
description: Use when running or recovering JobLand job discovery, enrichment, screening, or provider workflows through JobLandMCP.
---

# Job Pipeline

## Hard Rule

Use JobLandMCP only. Do not use local pipeline scripts, direct data clients, SQL, database files, or backend-specific knowledge. If a required pipeline action is not exposed by JobLandMCP, stop and report the missing MCP capability.

## JobLandMCP Tools

Use the `jobland` MCP server. Tool names may be exposed with a profile prefix; select the matching JobLandMCP tool from the available tool list.

Core record tools:
- `jobs_list`
- `jobs_get`
- `jobs_create`
- `jobs_update`
- `jobs_delete`
- `jobs_find_by_url`
- `jobs_search`

Interview tools:
- `interviews_list`
- `interviews_get`
- `interviews_create`
- `interviews_update`
- `interviews_delete`
- `interviews_search`

## Workflow Rules

- Reads may run without confirmation.
- Writes require explicit user intent or approval.
- For provider scraping, enrichment, screening, research, or notifications, use the corresponding JobLandMCP capability if it exists.
- Do not create temporary scripts, wrapper scripts, one-off snippets, SQL, or direct backend clients.
- Do not infer storage technology or schema internals. Treat JobLandMCP results as the source of truth.

## Status Lifecycle

Use record fields returned by JobLandMCP. Common job lifecycle values:

```
new -> enriched | enrich_failed -> screened
research_status = researched
user_status = applied | rejected | offer | withdrawn
```

If field names differ in the MCP response, use the returned field names rather than assuming hidden storage details.

## Recovery Pattern

1. Use `jobs_get`, `jobs_list`, `jobs_find_by_url`, or `jobs_search` to identify affected records.
2. Inspect returned status, URL, title, company, description, and assessment fields.
3. Use JobLandMCP write tools only when the user asked for the mutation.
4. If the recovery requires browser scraping, enrichment, batch screening, or notification and no MCP tool exposes it, report the missing MCP operation and stop.

## Provider Notes

- Browser authentication and provider UI behavior can still matter, but the skill must not call provider scripts directly.
- If the user needs to log in, open the provider login page in the visible browser and let the user enter credentials.
- For JobLeads, prefer the visible in-page search flow over assuming URL parameters are durable.
- For Wellfound, use the existing visible browser session when an MCP-backed scrape/enrich operation needs authenticated access.
