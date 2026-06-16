---
name: import-from-spreadsheet
description: Import jobs from external spreadsheets (Google Sheets, CSV exports) into the pipeline. Filter, ingest, enrich from CSV data, and batch-screen using existing pipeline scripts.
---

# Import from Spreadsheet

When the user shares a link to a Google Sheet / spreadsheet with job listings, or asks you to bulk-import jobs from a file.

## Workflow

### 1. Export sheet to CSV

Use `curl` to download as CSV:

```bash
curl -sL "https://docs.google.com/spreadsheets/d/<ID>/export?format=csv&gid=<TAB_ID>" \
  -A "Mozilla/5.0 ..." -o tmp/sheet.csv
```

- `gid` is the tab ID from the URL (`#gid=12345`).
- If blocked, retry with a more complete Chrome UA header.
- Check the CSV has the right columns and row count before proceeding.

### 2. Apply profile filter

Analyze the CSV structure: columns, job families, countries, titles. Write a filter script in `tmp/` that drops jobs against the user's profile.

Hard exclusions:
- Junior, intern, entry, graduate titles
- Non-SWE roles: QA, Sales Engineer, Field Service, Medical Coder, Lift/Elevator, Magento/Salesforce/WordPress dev, etc.
- US-only, India-only, LATAM-only, Asia-only locations; EU remote or fully remote only
- Salary clearly below threshold
- Mobile-only subcategories
- Microsoft/Oracle stacks such as Azure, .NET, SQL Server, based on user preference

Seniority requirement: title must contain Senior, Staff, Principal, Lead, Architect, Director, or Manager, or an Experience Level column must mark it as such.

Run the filter and output `tmp/filtered_dev.csv`.

### 3. Use the csvfeed provider

The reusable provider lives at `scripts/providers/csvfeed/` and reads `tmp/filtered_dev.csv`.

For a one-off import, temporarily add `csvfeed` to `PROVIDERS` in `scripts/scraping_pipeline.py`, run the import, then remove it again. Do not leave `csvfeed` enabled in the committed provider set.

The provider populates `ShallowJob` with url, title, company, location, country, salary_raw, posting_date, and dedup_key.

### 4. Ingest via pipeline

```bash
python3 scripts/scraping_pipeline.py --provider csvfeed
```

Enrichment will fail if Chrome is not running. The job IDs are assigned; descriptions are not set by the provider because `ShallowJob` has no description field.

### 5. Post-ingest: write descriptions from CSV

Do not write a custom permanent script. Use `db_write_job_fields.py`:

```bash
echo '{"title":"...","description":"...","location":"...","salary_range":"...","date_posted":"..."}' | \
  python3 scripts/db_write_job_fields.py --job-id <ID>
```

Then reset status from `enrich_failed` to `new`:

```python
from scripts.pb_client import get_pb
pb = get_pb()
for j in pb.get_list('jobs', filter="provider='csvfeed' && pipeline_status='enrich_failed'"):
    pb.update('jobs', j['id'], {'pipeline_status': 'new'})
```

### 6. Batch screening

Use the existing batch screening module:

```python
from scripts.pipeline.screen_jobs_batch import screen_jobs_batch

ok_ids, failures = screen_jobs_batch(job_ids, max_workers=5)
```

Each job gets a Telegram notification on completion via `_notify_screened()` in `screen_job.py`.

## Pitfalls

### csvfeed provider was left in PROVIDERS

Remove it from `PROVIDERS` after use to avoid confusing future pipeline runs.

### Description must be set post-ingest

`ShallowJob` has no `description` field. The ingest script does not write it either. After ingest, set descriptions via `db_write_job_fields.py` or the enrichment CDP step if Chrome is running. Without descriptions, screening produces weak verdicts.

### Dedup uses company+title key

The `dedup_key` is `"{company}::{title}"`. If the same job appears in the spreadsheet and was already scraped by a real provider, it will be deduped and not re-ingested.

### Screening uses DeepSeek API

`DEEPSEEK_API_KEY` must be in the environment or in `scripts/.env`. If not set, `screen_job.py` falls back to `_local_assessment()`, a keyword heuristic that produces low-quality verdicts. Check with:

```bash
python3 -c "import os; print(bool(os.environ.get('DEEPSEEK_API_KEY')))"
```

### Telegram notifications per job

Each screened job sends a Telegram notification. For large batches this can be noisy. The notification is best-effort; failures are silently swallowed.
