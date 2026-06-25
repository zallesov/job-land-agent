---
name: external-job-imports
description: Use when importing user-supplied job listings from spreadsheets, CSV exports, or tabular feeds into JobLand through JobLandMCP.
---

# External Job Imports

## Hard Rule

Use JobLandMCP only for JobLand records. Do not create local provider adapters, temporary import scripts, SQL, direct backend clients, or storage-specific write paths.

## Workflow

1. Inspect the source file or sheet in read-only mode.
2. Map columns to job fields: URL, title, company, location/country, salary, posting date, description.
3. Filter rows against the user's standing constraints before any write.
4. For each candidate row, use `jobs_find_by_url` to avoid duplicates.
5. If a JobLandMCP bulk import tool exists, use it.
6. Otherwise, ask for approval before creating records one by one with `jobs_create`.
7. After import, use MCP enrichment/screening tools only if available. If missing, report the missing MCP capability.

## Spreadsheet Pitfalls

- Treat geography and work mode as separate signals.
- `Remote` in a workplace-mode column does not prove worldwide eligibility.
- Produce a preview before writes: total rows, filtered rows, country/location breakdown, and title/company/URL samples.

## Verification

- Source inspected
- Rows filtered
- Duplicates checked through JobLandMCP
- User approved any creates
- Created records re-read through JobLandMCP
- Missing downstream MCP capabilities reported clearly
