# Plan 6: Next.js Job Dashboard

## Summary

Build a localhost-only Next.js App Router dashboard as the operator UI for the SQLite job pipeline. The dashboard reads directly from SQLite on the server, renders a dense list-and-detail triage workspace, supports URL-only manual job capture, lets the user edit workflow fields, and can trigger the `research_job` Hermes workflow.

V1 does not expose application draft generation or scraper runs from the UI.

## Key Changes

### App Shape

Create a new Next.js app in the local project using App Router.

Use:

- server components for SQLite-backed page rendering
- server actions for small workflow edits
- route handlers or server actions for Hermes command creation
- client components only for local interactivity: selecting a job, opening panels, submitting small forms

The app is localhost-only in v1 and does not need auth.

### Dashboard UI

Primary layout:

- dense job list
- persistent detail pane for selected job
- compact top filter bar
- command/status area in the detail pane

Job list should show:

- title
- company / posted company
- provider
- country/location/remote signal
- status
- relevance score
- trust score
- verdict
- first seen / last seen
- researched/unresearched indicator

Detail pane should show:

- original description
- source/apply links
- company research summary
- job assessment summary
- red flags
- notes/comments
- command status/errors
- event history excerpt

### Filters And Sorting

V1 first-class filters:

- status
- apply verdict
- relevance score range
- trust score range
- provider
- country
- remote signal
- researched/unresearched
- new only

Use simple indexed SQL queries. Do not add SQLite full-text search in v1.

Default sort:

1. unreviewed/new jobs first
2. higher relevance score
3. higher trust score
4. newest `first_seen`

### Manual Add And Editing

Manual add is URL-only:

- user enters a job URL
- server validates URL shape
- server dedupes by `jobs.url`
- if new, insert a job with status `new`, provider `manual`, and missing fields left blank
- write an `events` row

Editable fields in v1:

- `jobs.status`
- `jobs.comment`
- `jobs.current_interview_status`

Do not allow editing source-owned or research-owned fields from the dashboard in v1.

### Research Command

The job detail pane exposes one command button:

```text
Research job
```

Behavior:

- validates job id
- creates or reuses an `agent_commands` row for `research_job`
- starts Hermes through the allowlisted server-side CLI trigger
- returns immediately
- displays queued/running/failed/succeeded status after page refresh

No automatic polling in v1. The user refreshes or revisits the page to see completed research.

## Test Plan

- Render dashboard from an empty SQLite DB without crashing.
- Render job list and detail pane from seeded jobs, assessments, and company research.
- Verify filters generate correct SQL results.
- Add a manual URL and verify a `manual` provider job is inserted once.
- Add the same manual URL twice and verify dedupe returns the existing job.
- Edit status/comment/current interview status and verify source/research fields are unchanged.
- Trigger `research_job` and verify an `agent_commands` row is created or reused.
- Verify unsupported commands are not exposed in the UI.
- Verify failed command errors are visible in the detail pane after refresh.

## Assumptions

- Next.js uses App Router.
- SQLite access happens only on the server.
- Dashboard is localhost-only and unauthenticated for v1.
- V1 exposes `Research job` only; application draft generation comes after the application worker is planned.
- Manual URL-only rows may have blank title/company/description until a later enrichment or research step fills them.
