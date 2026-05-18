# Plan 7: Telegram Notifications

## Summary

Hermes owns all Telegram delivery. The job pipeline should not introduce a separate notification service. V1 sends daily digests, scraper/pipeline failure alerts, and research completion/failure notifications. Messages stay compact and actionable; full details remain in SQLite and the dashboard.

## Notification Events

Send Telegram messages for:

- daily pipeline completion
- daily pipeline partial/failure status
- provider scraper failure
- ingestion failure
- research command success
- research command failure

Do not notify for manual dashboard edits, duplicate job inserts, status changes, or every individual database event in v1.

## Daily Digest

Send one digest after the daily pipeline finishes.

Include:

- run status: `succeeded`, `partial`, or `failed`
- number of new jobs inserted
- new jobs grouped by provider
- all new jobs as compact one-line entries
- source/apply URL per job where available
- dashboard link/path per job when available
- failed providers or failed steps, if any

Use first SQLite insert as the definition of "new job".

If there are zero new jobs and all providers succeeded, still send a quiet heartbeat:

```text
Daily jobs run OK
New jobs: 0
Providers: greenhouse OK, jobleads OK
```

## Failure Alerts

Failure messages must be compact and actionable.

Template:

```text
Job pipeline failure
Provider/step: greenhouse scrape
Run status: partial
Error: <short error>
Artifacts/logs: outputs/greenhouse/runs/...
Action: fix scraper with Codex before next run
```

Rules:

- Do not send full logs.
- Include enough path/context to find the artifact.
- A failed provider does not block notifications for successful providers.
- No automatic retries in v1.

## Research Notifications

On successful `research_job`, send:

```text
Research complete
<Title> - <Company>
Verdict: Apply with caution
Relevance: 84
Trust: 62
Reason: <one-line summary>
Dashboard: <local dashboard link/path>
Source: <job/apply URL>
```

On failed `research_job`, send:

```text
Research failed
<Title> - <Company>
Error: <short error>
Dashboard: <local dashboard link/path>
Action: inspect command error and rerun from dashboard
```

Full research notes, citations, red flags, and source URLs stay in the dashboard.

## Implementation Notes

- Hermes reads notification data from SQLite after each workflow.
- Telegram formatting should be plain and robust, avoiding long markdown-heavy messages.
- Dashboard links may be local-only; always include source/apply URLs when available.
- Each sent notification should write an `events` row or be referenced in the related `pipeline_runs.summary_json` / `agent_commands.result_json`.

## Test Plan

- Daily run with new jobs sends all new jobs grouped by provider.
- Daily run with zero new jobs sends quiet success heartbeat.
- One provider failure sends actionable failure alert and still sends available successful new jobs.
- Ingestion failure sends compact failure alert with run/log context.
- Successful research command sends verdict, relevance score, trust score, reason, dashboard link, and source URL.
- Failed research command sends short error and dashboard/action guidance.
- Verify manual status/comment edits do not send Telegram messages.

## Assumptions

- Hermes already has Telegram credentials and delivery working.
- Hermes is the only component that sends Telegram messages.
- Next.js does not send Telegram directly.
- Telegram messages are operational summaries, not the source of record.
