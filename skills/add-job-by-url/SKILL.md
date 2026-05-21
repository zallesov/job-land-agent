---
name: add-job-by-url
description: Add a single job by URL. Deduplicates, ingests, enriches, and sanity-checks. Works from Hermes chat, Telegram, or dashboard. Triggered when user provides a job posting URL.
---

# Add Job by URL

## Trigger

Any message that contains a job posting URL (e.g., `https://boards.greenhouse.io/...`, `https://wellfound.com/jobs/...`, `https://jobleads.com/...`, any `https://` URL that looks like a job posting).

Also triggered by: "add this job", "track this job", "add job by url".

## Execution Rules

- Execute immediately without asking for confirmation.
- Do NOT enrich if duplicate is detected.
- Uses the same pipeline functions as the automated scraper — do not reimplement.

## Step 1: Read db_path from config

```bash
python3 -c "import yaml; d=yaml.safe_load(open('config/user.yaml')); print(d.get('db_path','jobs.db'))"
```

## Step 2: Check for duplicate

```bash
python3 -c "
import sqlite3, sys
db = '<db_path>'
url = '<url>'
con = sqlite3.connect(db)
row = con.execute('SELECT id FROM jobs WHERE url=?', (url,)).fetchone()
if row:
    print(f'DUPLICATE:{row[0]}')
else:
    print('NEW')
con.close()
"
```

If `DUPLICATE:<id>`: report "Already tracked as job ID N" and stop.

## Step 3: Ingest minimal job record

```bash
python3 -c "
import sys, json
sys.path.insert(0, '.')
from scripts.pipeline.types import ShallowJob
from scripts.pipeline.ingest import ingest_jobs
url = '<url>'
job = ShallowJob(
    provider='manual',
    title='',
    company='',
    url=url,
    location='',
    country=None,
    dedup_key=url,
    posting_date=None,
    salary_raw=None,
)
ids = ingest_jobs([job], db_path='<db_path>')
print(ids[0])
"
```

Capture the job_id.

## Step 4: Enrich the job

```bash
python3 -c "
import sys
sys.path.insert(0, '.')
from scripts.pipeline.enrich_job import enrich_job
result = enrich_job(<job_id>, db_path='<db_path>')
print('success:', result.success)
if result.error:
    print('error:', result.error)
"
```

If enrichment fails: report error and stop (job is still in DB with status `enrich_failed`).

## Step 5: Sanity check

```bash
python3 -c "
import sys
sys.path.insert(0, '.')
from scripts.pipeline.sanity_check_job import sanity_check_job
result = sanity_check_job(<job_id>, db_path='<db_path>')
print('success:', result.success, 'data:', result.data)
"
```

## Step 6: Report result

Read the job record and report:

```bash
python3 -c "
import sqlite3, json
con = sqlite3.connect('<db_path>')
con.row_factory = sqlite3.Row
row = con.execute('SELECT id, title, posted_company_name, status, url FROM jobs WHERE id=?', (<job_id>,)).fetchone()
print(json.dumps(dict(row)))
con.close()
"
```

Report to user:
```
✅ Job added: #<id>
  Title: <title>
  Company: <company>
  Status: <status>
  Dashboard: http://localhost:3000
```

If `status = sanity_failed`: add "⚠️ Sanity check failed — job may not match your profile. Check dashboard for details."
