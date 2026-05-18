# Plan 2: Scraper Outputs And SQLite Ingestion

## Summary

Make provider scraping deterministic and provider-owned, while centralizing all SQLite writes in one ingestion layer. Each provider scraper produces a normalized JSON array artifact under `outputs/<provider>/runs/`. The ingestion command reads those artifacts, dedupes by URL, creates/links company records, inserts new jobs, and updates only safe machine-owned fields on existing jobs.

## Key Changes

### Provider Artifacts

Each provider writes one normalized JSON array per run:

```text
outputs/<provider>/runs/<provider>_jobs_live_YYYY-MM-DD.json
```

Each job object must use the shared shape:

```json
{
  "provider": "greenhouse",
  "providerJobId": "optional",
  "url": "https://...",
  "applyUrl": "https://...",
  "company": "Company Name",
  "title": "Role Title",
  "description": "Full text",
  "location": "Berlin",
  "country": "Germany",
  "remoteScope": "remote",
  "datePosted": "2026-05-18",
  "sourcePayload": {}
}
```

Provider-specific/debug data goes into `sourcePayload`. Optional raw screenshots, HTML, console logs, or downloads stay beside the run artifact for troubleshooting, but ingestion only depends on the normalized JSON array.

### Provider Config

Each provider skill owns a small config file:

```text
.codex/skills/<provider>/provider.yaml
```

The config defines:

- provider id/name
- enabled flag
- search URLs or search permutations
- default output directory
- required auth notes
- expected countries/locations
- optional scrape limits

Adding a provider means adding a provider folder/config/script, not editing the ingestion schema.

### Ingestion Behavior

Add a single ingestion command:

```bash
python scripts/ingest_provider_outputs.py --db jobs.db --run-file outputs/greenhouse/runs/greenhouse_jobs_live_2026-05-18.json
```

Also support batch ingestion:

```bash
python scripts/ingest_provider_outputs.py --db jobs.db --all-latest
```

Rules:

- Job URL is the canonical dedupe key.
- New URL inserts a `jobs` row and creates/links a `companies` row.
- Existing URL updates only machine-owned fields:
  - `last_seen`
  - `apply_url` if currently blank and new value exists
  - `description` if currently blank and new value exists
  - `source_payload_json`
  - `updated_at`
- Existing URL never overwrites:
  - `status`
  - `comment`
  - `current_interview_status`
  - application state
  - assessment state
- Company identity uses domain first when available; otherwise normalized company name.
- Each insert/update writes an `events` row for auditability.
- Each ingestion run writes a `pipeline_runs` summary with inserted, updated, skipped, and failed counts.

### Failure Handling

Use partial success:

- If one provider scraper fails, other provider artifacts can still be ingested.
- Failed provider steps are recorded in `pipeline_runs.summary_json`.
- Ingestion validates each artifact before writing; malformed artifacts fail that provider/run only.
- Telegram digest should mention failed providers separately from successful new-job counts.

### New Job Definition

A job is "new" only when its URL is first inserted into SQLite. Telegram updates and dashboard badges use this canonical insert event, not provider artifact appearance.

## Test Plan

- Ingest a valid provider JSON array into an empty DB and verify inserted job/company rows.
- Re-ingest the same artifact and verify no duplicate jobs.
- Re-ingest an existing job with a new `last_seen` and verify manual fields are unchanged.
- Ingest two jobs with the same company/domain and verify one company record.
- Ingest malformed provider JSON and verify no partial writes for that artifact plus a failed run record.
- Ingest one successful and one failed provider run and verify partial success summary.
- Verify new-job count equals first-time SQLite inserts only.

## Assumptions

- Provider scrapers are deterministic scripts run by Hermes, not interactive Codex sessions.
- Provider outputs are normalized JSON arrays for v1.
- SQLite is fresh for v1; legacy XLSX files are not imported initially.
- Ingestion owns all canonical job/company writes.
- Provider scripts may keep raw/debug artifacts, but those are not canonical data.
