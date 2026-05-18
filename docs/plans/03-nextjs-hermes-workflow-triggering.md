# Plan 3: Next.js To Hermes Workflow Triggering

## Summary

Next.js will trigger selected Hermes workflows from server-side API routes using an allowlisted Hermes CLI mapping. The browser never sends raw shell commands. UI actions create command/run records in SQLite, start Hermes asynchronously, and immediately return a command id. The dashboard polls SQLite for status and results.

This gives immediate UI-triggered research/apply workflows while keeping Hermes as the workflow runner.

## Key Changes

### Trigger Model

Add a server-only command trigger layer in the Next.js app:

```text
UI button
  -> Next.js server API/action
  -> validate action + payload
  -> create/reuse agent_commands row
  -> spawn allowlisted Hermes CLI command
  -> return command id immediately
  -> dashboard polls command status
```

The API must only accept typed actions, not arbitrary command strings.

Initial allowed UI-triggered workflows:

- `research_job`
- `generate_application_draft`

Scraping and ingestion remain scheduled Hermes workflows for v1.

### Hermes CLI Allowlist

Map each UI action to a fixed Hermes invocation:

```text
research_job:
  hermes run research_job --command-id <id>

generate_application_draft:
  hermes run generate_application_draft --command-id <id>
```

Hermes reads `agent_commands.payload_json` by `command-id`, executes the workflow, and updates:

- `agent_commands.status`
- `started_at`
- `finished_at`
- `result_json`
- `error`

Workflow scripts called by Hermes still use stable local contracts:

```bash
python scripts/research_job.py --db jobs.db --job-id 123
python scripts/generate_application_draft.py --db jobs.db --job-id 123
```

### API Behavior

For each trigger request:

- Validate that the job exists.
- Validate that the requested action is allowlisted.
- Validate payload shape, normally `{ "job_id": number }`.
- If the same command type for the same job is already `pending` or `running`, return the existing command id.
- Otherwise insert a new `agent_commands` row with `status = pending`, `created_by = ui`.
- Spawn Hermes in the background.
- Return immediately with `{ commandId, status }`.
- Never wait for research/apply completion inside the HTTP request.

### Dashboard Behavior

- Buttons show immediate feedback after command creation.
- Pending/running commands are visible on the job row.
- The UI polls or refreshes command status from SQLite.
- On success:
  - `research_job` shows updated assessment/research fields.
  - `generate_application_draft` shows generated file paths and application status.
- On failure, show the stored error and allow retry after the failed command is no longer running.

### Safety Rules

- No raw command execution from user input.
- No arbitrary Hermes workflow names from the browser.
- No duplicate pending/running commands for the same job/action.
- API is localhost-only for v1.
- Application draft workflow does not submit applications.

## Test Plan

- Trigger `research_job` for a valid job and verify an `agent_commands` row is created.
- Trigger the same `research_job` twice while pending/running and verify the second call returns the existing command id.
- Trigger an unsupported action and verify it is rejected.
- Trigger a command for a missing job id and verify it is rejected.
- Verify the API returns immediately and does not wait for Hermes completion.
- Simulate Hermes success and verify the dashboard displays updated status/result.
- Simulate Hermes failure and verify `error` is visible and retry is possible.
- Verify generated application draft command records an `applications` row but does not submit anything.

## Assumptions

- Hermes provides a CLI command shape equivalent to `hermes run <workflow> --command-id <id>`.
- If Hermes uses different exact CLI syntax, only the server-side allowlist mapping changes.
- Next.js runs locally and can spawn the Hermes CLI from its server runtime.
- SQLite remains the source of truth for command status and results.
- Daily scraping/ingestion stays scheduled in Hermes and is not UI-triggered in v1.
