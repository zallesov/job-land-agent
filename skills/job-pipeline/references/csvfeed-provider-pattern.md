# csvfeed Provider Pattern — File-Based Job Injection

Inject pre-filtered job lists from spreadsheets/CSVs into the pipeline without CDP scraping.

## When to use

- User shares a Google Sheet or exported CSV containing curated job listings
- Need to filter 500-1000+ jobs against a profile before ingestion
- Chrome is not available or CDP enrichment would be too slow for the volume

## Pattern Overview

```
Google Sheet → CSV export → filter script → csvfeed provider → ingest → post-ingest enrichment → batch screening
```

## Step 1: Export Sheet to CSV

```bash
curl -sL "https://docs.google.com/spreadsheets/d/<SPREADSHEET_ID>/export?format=csv&gid=<TAB_GID>" -o tmp/raw_sheet.csv
```

The `gid` parameter selects a specific tab. Find it in the URL (`#gid=821747821`).

## Step 2: Filter Against Profile

Write a Python filter script that applies:
- **Seniority**: Senior/Staff/Principal/Lead/Architect/Director (exclude Junior, Intern, Entry, Associate, Mid)
- **Location**: Remote, EU countries (exclude US-only, India, LATAM, Asia)
- **Role type**: Backend/Full Stack/DevOps/Cloud/Platform (exclude QA/Sales/Field/Medical/Magento/Salesforce)
- **Title patterns**: Exclude non-SWE titles (mechanical, field service, lift engineer, etc.)
- **Salary floor**: >= 80K USD / 60K EUR / 45K GBP

Write filtered results to `tmp/filtered_dev.csv`.

## Step 3: Create csvfeed Provider

### `scripts/providers/csvfeed/check_auth.py`

```python
def check_auth(cdp_url: str) -> bool:
    return True  # Always passes — no auth needed
```

### `scripts/providers/csvfeed/scrape_jobs.py`

Reads filtered CSV, returns `list[ShallowJob]`. Key fields:
- `provider="csvfeed"` — marks the provider for later queries
- `dedup_key=f"{company}::{title}"` — standard dedup
- `status="new"` — no filtering at ingest time

### Registration

Add `"csvfeed"` to the `PROVIDERS` set in `scripts/scraping_pipeline.py`.

## Step 4: Run Pipeline

```bash
python3 scripts/scraping_pipeline.py --provider csvfeed
```

This ingests jobs but enrichment **will fail** if Chrome is not running (CDP connection refused). This is expected — csvfeed jobs already have descriptions in the CSV.

## Step 5: Post-Ingest Enrichment

After ingest, write descriptions from CSV to DB for each job:

```python
import json, subprocess
# For each ingested job (matched by URL):
fields = {"title": ..., "description": ..., "location": ..., "salary_range": ...}
result = subprocess.run(
    ["python3", "scripts/db_write_job_fields.py", "--db", "jobs.db", "--job-id", str(job_id)],
    input=json.dumps(fields), capture_output=True, text=True
)
```

Then reset status:
```bash
python3 -c "from scripts.db import get_connection; con=get_connection('jobs.db'); con.execute(\"UPDATE jobs SET status='new', pipeline_status='new', updated_at=datetime('now') WHERE provider='csvfeed' AND status='enrich_failed'\"); con.commit(); con.close()"
```

## Step 6: Batch Screening

```bash
python3 -c "
import sys; sys.path.insert(0, 'scripts')
from pipeline.screen_jobs_batch import screen_jobs_batch
import sqlite3
con = sqlite3.connect('jobs.db')
ids = [str(r[0]) for r in con.execute(\"SELECT id FROM jobs WHERE provider='csvfeed' AND status='new' ORDER BY id\").fetchall()]
con.close()
ok_ids, failures = screen_jobs_batch(ids, max_workers=5)
print(f'{len(ok_ids)} ok, {len(failures)} failed')
"
```

Use `max_workers=5` for parallelism. The `.env` file is loaded automatically by `screen_job.py` for `DEEPSEEK_API_KEY`.

## Pitfalls

### No ShallowJob.description field

`ShallowJob` (in `scripts/pipeline/types.py`) has no `description` field. The ingest script only writes: url, apply_url, provider, posted_company_name, title, location, country, date_posted, salary_range, dedup_key, status, pipeline_status. Descriptions must be set post-ingest via `db_write_job_fields.py`.

### Pipeline processes enrichment before screen

The pipeline does: ingest → enrich (per job) → screen (per job). If enrich fails, no job reaches screening. Post-ingest enrichment fixes this by filling descriptions and resetting status, then you run batch screening separately.

### No success notification from pipeline

`send_daily_digest()` only fires on failure. However, per-job Telegram notifications are now sent by `_notify_screened()` in `screen_job.py` for every successfully screened job. The format is `{icon} #{job_id} {verdict} R:{score}` with job details. These fire for all success paths regardless of whether screening used DeepSeek API or local heuristic.

### Dedup across runs

csvfeed jobs are deduped by `company::title`. If you re-export the same sheet, the same jobs will be skipped. This is correct behavior — pipeline only ingests genuinely new entries on subsequent runs.
