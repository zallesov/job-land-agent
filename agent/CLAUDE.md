# JobLandAgent — Claude Directives

Part of the `joblandagent` monorepo (`~/joblandagent/`). This directory is the agent working root.

## Skills Location

All project skills live in `skills/`. Never create skills outside this directory.

## JobLand Data Access

All JobLand job and interview records must be accessed through the configured JobLandMCP server.

Do not use local scripts, direct backend clients, SQL, database files, migration tooling, or storage-specific assumptions for JobLand records. If a requested operation is not available through JobLandMCP, report the missing MCP capability instead of bypassing it.

## Browser Work

Use the visible authenticated browser for provider login, scraping-like inspection, enrichment-like inspection, and application forms. The user should be able to watch browser interactions.

## Dashboard

The dashboard is outside the agent skills workflow. Do not reintroduce a dashboard skill here.
