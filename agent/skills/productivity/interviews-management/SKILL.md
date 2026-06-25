---
name: interviews-management
description: Use when listing, reconciling, creating, or updating JobLand interview records through JobLandMCP.
---

# Interviews Management

## Hard Rule

Use JobLandMCP only. Do not use local scripts, SQL, direct backend clients, database files, or storage-specific terminology.

## JobLandMCP Tools

- `interviews_list`
- `interviews_get`
- `interviews_create`
- `interviews_update`
- `interviews_delete`
- `interviews_search`

Use job tools (`jobs_get`, `jobs_search`, `jobs_list`) only to connect interview context to a job record.

## Workflow

1. Read existing interview records with MCP.
2. Gather evidence from Gmail, Calendar, user messages, or job records.
3. Build a proposed change set.
4. Ask before creating, updating, or deleting interview records unless the user explicitly requested the write.
5. Apply approved changes through MCP tools.
6. Re-read changed records through MCP and summarize the result.

## Record Handling

- Treat ids as opaque JobLand ids.
- Use fields returned by MCP; do not assume hidden schema details.
- Prefer updating existing records over creating duplicates.
- Never hard-delete unless the user explicitly asks for deletion.
