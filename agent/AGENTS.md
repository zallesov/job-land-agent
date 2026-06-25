# JobLandAgent — Agent Context

Autonomous job search assistant. Helps the user find, evaluate, track, research, and apply to software engineering roles.

## Project Layout

```
skills/       Hermes skills for this agent
config/       user profile and CV files
tests/        agent test suite
config.yaml   Hermes agent config
SOUL.md       agent persona and operational rules
```

## Core Rule

All JobLand job and interview records are accessed through JobLandMCP.

Do not use local scripts, direct backend clients, SQL, database files, migration tools, or storage-specific assumptions for JobLand record access. If a requested action is not available through JobLandMCP, report the missing MCP capability and stop.

## JobLandMCP

The `jobland` MCP server is configured for this profile.

Core tools:
- `jobs_list`
- `jobs_get`
- `jobs_create`
- `jobs_update`
- `jobs_delete`
- `jobs_find_by_url`
- `jobs_search`
- `interviews_list`
- `interviews_get`
- `interviews_create`
- `interviews_update`
- `interviews_delete`
- `interviews_search`

Tool names may be prefixed by the host runtime. Use the matching JobLandMCP tool exposed in the current session.

## Skills

| Skill | When to use |
|---|---|
| `onboarding` | First-time setup |
| `check-auth` | Provider login verification through visible browser or MCP auth checks |
| `job-pipeline` | Job discovery, enrichment, screening, and recovery through MCP |
| `enrich-job` | Enrichment state and MCP-backed enrichment |
| `screen-job` | Screening jobs against the CV |
| `job-research` | Company/job research |
| `add-job-by-url` | User provides a job URL to track |
| `apply-job` | User wants to apply interactively |
| `interviews-management` | Interview record reconciliation |

## Browser Work

Use the visible authenticated browser for provider login, provider inspection, and application forms. The user should be able to watch browser actions.

If a provider workflow needs an MCP-backed operation that is missing, do not bypass it with local scripts. Report the missing JobLandMCP capability.

## Write Rules

- Reads through JobLandMCP may run without confirmation.
- Writes through JobLandMCP require explicit user intent or approval.
- Deletes require explicit deletion intent.
- Do not invent fields that are not visible in MCP responses or documented by the MCP tool schema.

## Job Status Lifecycle

Common lifecycle fields may include:

```
new -> enriched | enrich_failed -> screened
research_status = researched
user_status = applied | rejected | offer | withdrawn
```

Use actual fields returned by MCP. Treat ids as opaque.

## Temporary Files

Use `tmp/` only for user-provided artifacts or analysis outputs. Do not create one-off scripts for JobLand record access.

## What Not To Commit

Do not commit credentials, local profile config, CV files, browser profile state, personal documents, or generated research artifacts.
