---
name: add-job-by-url
description: Add a single job by URL. Runs the same dedup → ingest → enrich → screen pipeline as the automated scraper. Triggered when user provides a job posting URL.
---

# Add Job by URL

## Trigger

Any message containing a job posting URL (e.g. `https://boards.greenhouse.io/...`, `https://wellfound.com/jobs/...`, any `https://` URL that looks like a job posting).

Also triggered by: "add this job", "track this job", "add job by url".

## Execution Rules

- Execute immediately without asking for confirmation.
- Manual jobs always use `status="new"` — skip the relevance filter (user intentionally adding).
- Same dedup → ingest → enrich → screen chain as `scripts/scraping_pipeline.py`.

## Step 1: Read db_path

```bash
python3 -c "import yaml; d=yaml.safe_load(open('config/user.yaml')); print(d.get('db_path','jobs.db'))"
```

## Step 2: Run pipeline (dedup → ingest → enrich → screen)

```bash
python3 - <<'EOF'
import sys
sys.path.insert(0, '.')
from scripts.pipeline.types import ShallowJob
from scripts.pipeline.dedup import dedup_jobs
from scripts.pipeline.ingest import ingest_jobs
from scripts.pipeline.enrich_job import enrich_job
from scripts.pipeline.screen_job import screen_job

DB = '<db_path>'
URL = '<url>'

job = ShallowJob(
    provider='manual',
    title='',
    company='',
    url=URL,
    location='',
    country=None,
    dedup_key=URL,
    posting_date=None,
    salary_raw=None,
    status='new',
)

new = dedup_jobs([job], db_path=DB)
if not new:
    print('DUPLICATE')
    sys.exit(0)

ids = ingest_jobs(new, db_path=DB)
job_id = ids[0]
print(f'INGESTED:{job_id}')

result = enrich_job(job_id, db_path=DB)
if not result.success:
    print(f'ENRICH_FAILED:{result.error}')
    sys.exit(0)
print('ENRICHED')

result = screen_job(job_id, db_path=DB)
if not result.success:
    print(f'SCREEN_FAILED:{result.error}')
    sys.exit(0)
print('SCREENED')
EOF
```

Parse output:
- `DUPLICATE` → report "Already tracked" and stop
- `ENRICH_FAILED:<err>` → report error, stop (job in DB with `enrich_failed`)
- `SCREEN_FAILED:<err>` → report error, stop (job in DB with `screen_failed`)
- `SCREENED` → continue to Step 3

## Step 3: Report result

```bash
python3 -c "
import sqlite3, json
con = sqlite3.connect('<db_path>')
con.row_factory = sqlite3.Row
job = con.execute('SELECT j.id, j.title, j.posted_company_name, j.status FROM jobs j WHERE j.id=?', (<job_id>,)).fetchone()
ass = con.execute('SELECT apply_verdict, relevance_score, one_line_summary FROM job_assessments WHERE job_id=?', (<job_id>,)).fetchone()
print(json.dumps({'job': dict(job), 'assessment': dict(ass) if ass else {}}))
con.close()
"
```

Report to user:
```
✅ Job added: #<id>
  Title: <title>
  Company: <company>
  Verdict: <apply_verdict>  (R:<relevance_score>)
  <one_line_summary>
  Dashboard: http://localhost:3000
```

If `status = screen_failed`: "⚠️ Screen failed — check dashboard for details."
