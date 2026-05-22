---
name: daily-pipeline
description: Use when running the autonomous daily job pipeline. Scrapes greenhouse and jobleads, ingests into SQLite, tags new jobs, sends Telegram digest.
---

# Daily Job Pipeline

## Overview

Run the full daily job pipeline for the autonomous job search system.

Work directory: `/Users/zall/interviews`
DB: `/Users/zall/interviews/jobs.db`

## Pipeline Steps

### Step 1: Record pipeline start

Save the pipeline run ID for use in Step 6:

```bash
python3 -c "
import sys; sys.path.insert(0, 'scripts')
from db import get_connection, create_pipeline_run
con = get_connection('jobs.db')
run_id = create_pipeline_run(con, 'daily_pipeline')
con.commit()
print(run_id)
" > /tmp/hermes_pipeline_run_id.txt
```

### Step 1.5: Auth Gate (Greenhouse)

Verify the Greenhouse session is alive before scraping. This saves time — if the session expired, both scrapers will fail.

```bash
# Quick CDP check: navigate to dashboard, confirm "Welcome back" is visible.
# If redirected to /users/sign_in, abort and ask user to re-auth at https://my.greenhouse.io
```

Use `my.greenhouse.io` (candidate portal), NOT `app.greenhouse.io` (employer portal). See `greenhouse-scraper` skill for full auth check procedure.

### Step 2: Scrape Greenhouse

Use the `greenhouse-daily-export` skill to scrape and save:
`outputs/greenhouse/runs/greenhouse_jobs_live_YYYY-MM-DD.json`

If this step fails:
1. Record the failure
2. Run this to notify:
```bash
python3 scripts/telegram_notify.py \
  --type pipeline_failure \
  --provider greenhouse \
  --step scrape \
  --error "<short error summary>" \
  --artifact-path "outputs/greenhouse/runs/"
```
3. Continue to Step 3 (do not stop).

### Step 3: Scrape JobLeads

Use the `jobleads-daily-export` skill to scrape and save:
`outputs/jobleads/runs/jobleads_jobs_live_YYYY-MM-DD.json`

If this step fails:
1. Run failure notification (same pattern as Step 2 but provider=jobleads)
2. Continue to Step 4.

### Step 4: Ingest successful artifacts

```bash
cd /Users/zall/interviews && python3 scripts/ingest_provider_outputs.py --db jobs.db --all-latest
```

### Step 5: Tag new jobs

```bash
cd /Users/zall/interviews && python3 scripts/tag_new_jobs.py --db jobs.db --since-hours 25
```

### Step 6: Send Telegram digest

```bash
cd /Users/zall/interviews
RUNID=$(cat /tmp/hermes_pipeline_run_id.txt)
python3 scripts/telegram_notify.py --type daily_digest --db jobs.db --run-id "$RUNID"
```

## Failure Handling

- Provider failures: notify and continue. Do not abort the pipeline.
- Ingestion failure: notify with `--type pipeline_failure --provider all --step ingest`.
- Do not send full logs to Telegram.
- Next scheduled run is unaffected by today's failure.

## Output

Pipeline run recorded in `pipeline_runs` table.
New jobs visible in dashboard at `http://localhost:3000`.
Telegram digest sent after completion.
