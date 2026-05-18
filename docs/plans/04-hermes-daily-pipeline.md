# Plan 4: Hermes Daily Pipeline

## Summary

Hermes runs the autonomous daily collection pipeline once every morning in Europe/Madrid time. The daily pipeline scrapes enabled providers, ingests successful provider artifacts into SQLite, applies light fit tagging, and sends a compact Telegram summary.

Daily runs do not perform full AI research in v1. Research is triggered manually from the dashboard.

## Pipeline Flow

Run once per morning on the existing Hermes scheduler:

```text
daily_pipeline
  -> start pipeline_runs row
  -> scrape enabled providers
  -> ingest successful provider artifacts
  -> apply light tags to new jobs
  -> send Telegram summary
  -> finish pipeline_runs row
```

Provider scraper behavior:

- Each provider is an isolated step.
- If a provider scraper fails, do not retry.
- Record the provider failure in `pipeline_runs.summary_json`.
- Send an actionable compact Telegram failure notice.
- Continue with other providers that can still run.
- Keep the next scheduled daily run intact; scraper repair is handled manually with Codex.

## Ingestion And Tagging

Ingest only artifacts from provider steps that succeeded.

New jobs are defined by first insert into SQLite by URL. Existing jobs may update only safe machine-owned fields according to the ingestion plan.

After ingestion, apply cheap non-AI tags to newly inserted jobs:

- likely role family from title/description keywords
- likely seniority
- likely AI relevance
- country/location match
- remote signal
- missing salary signal
- recruiter/intermediary hint where obvious from provider data

Light tags are used only for ordering and dashboard/digest hints. They must not delete, suppress, or archive jobs.

## Telegram Notifications

Send one daily digest after ingestion:

- run status: succeeded, partial, or failed
- number of new jobs inserted
- new jobs by provider
- compact list of top newly inserted jobs using light tags/source fields
- dashboard link or local path reference if available
- failed provider steps, if any

Failure messages should be compact and actionable:

```text
Provider: greenhouse
Step: scrape
Error: short error summary
Artifacts/logs: outputs/greenhouse/runs/...
Action: fix scraper with Codex before next run
```

Do not send full logs to Telegram.

## Logging And Artifacts

- Keep run artifacts forever.
- Each provider writes dated artifacts under `outputs/<provider>/runs/`.
- Each pipeline execution writes a `pipeline_runs` row.
- Each important job insert/update writes an `events` row.
- Provider failure records include enough detail to find the relevant artifact/log path.

## Test Plan

- Run daily pipeline with all providers succeeding and verify jobs are ingested plus Telegram summary is generated.
- Simulate one provider scraper failure and verify other providers still ingest.
- Verify failed provider has no retry and failure appears in `pipeline_runs.summary_json`.
- Verify Telegram failure message includes provider, step, short error, and artifact/log path.
- Verify daily run does not trigger full AI research.
- Verify light tags are added only as hints and do not delete/archive/suppress jobs.
- Verify next scheduled run is unaffected by today's failure.

## Assumptions

- Hermes owns scheduling and Telegram delivery.
- Exact cron syntax lives in Hermes config, but target schedule is morning Europe/Madrid time.
- Scraper failures are repaired manually with Codex after notification.
- Daily pipeline may finish with `partial` status when at least one provider succeeds and at least one fails.
- Full research remains dashboard-triggered in v1.
