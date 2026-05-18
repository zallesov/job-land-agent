# Master Plan: Autonomous Job Pipeline

## Summary

Build an autonomous local job pipeline that collects jobs from multiple providers, stores canonical state in SQLite, shows a dense Next.js dashboard, lets the user trigger research from the UI, and uses Hermes for scheduled automation and Telegram notifications.

The system is organized around stable, reusable pieces:

- Hermes owns orchestration, scheduling, workflow execution, and Telegram delivery.
- SQLite owns canonical operational state.
- Deterministic scraper scripts produce provider run artifacts.
- A single ingestion layer writes jobs and companies into SQLite.
- Next.js provides the local operator dashboard.
- Research and application workflows are reusable scripts triggered by Hermes.
- Codex is used for development, repair, debugging, and manual operation, not unattended daily runtime.

## Architecture

```text
Hermes daily schedule
  -> deterministic provider scrapers
  -> normalized provider artifacts
  -> SQLite ingestion
  -> light tagging
  -> Telegram digest

Next.js localhost dashboard
  -> server-side SQLite reads
  -> workflow field edits
  -> manual URL capture
  -> creates agent command rows
  -> triggers allowlisted Hermes CLI workflows

Hermes workflows
  -> research/apply scripts
  -> SQLite updates
  -> Telegram status/result notifications
```

## Step Plans

- [Plan 1: SQLite Canonical Store](01-sqlite-canonical-store.md)
- [Plan 2: Scraper Outputs And SQLite Ingestion](02-scraper-outputs-and-ingestion.md)
- [Plan 3: Next.js To Hermes Workflow Triggering](03-nextjs-hermes-workflow-triggering.md)
- [Plan 4: Hermes Daily Pipeline](04-hermes-daily-pipeline.md)
- [Plan 5: Research Worker](05-research-worker.md)
- [Plan 6: Next.js Job Dashboard](06-nextjs-job-dashboard.md)
- [Plan 7: Telegram Notifications](07-telegram-notifications.md)

## Implementation Order

1. Create the SQLite schema and shared DB access layer.
2. Convert provider outputs to normalized JSON arrays and build SQLite ingestion.
3. Wire Hermes daily scraping and ingestion.
4. Build the research worker against SQLite.
5. Build the Next.js dashboard with read/edit/research-trigger capabilities.
6. Wire Telegram digests and workflow notifications.
7. Add application draft generation after the dashboard/research loop is stable.

## Operating Rules

- Jobs dedupe by URL.
- Companies dedupe by domain first, then normalized name.
- Manual workflow fields are user-owned and must not be overwritten by scrapers or research:
  - `status`
  - `comment`
  - `current_interview_status`
- Provider scrapers do not write directly to canonical job tables.
- Next.js does not execute raw user-provided commands.
- Telegram messages are operational summaries, not the source of record.
- Existing XLSX files remain legacy/reference artifacts for v1.

## Assumptions

- Hermes is already configured for daily execution and Telegram delivery.
- Next.js is localhost-only for v1 and does not require authentication.
- SQLite starts fresh for v1.
- Research is UI-triggered in v1, not part of the daily pipeline.
- Application submission is out of scope for v1; a future apply workflow generates draft materials only.
