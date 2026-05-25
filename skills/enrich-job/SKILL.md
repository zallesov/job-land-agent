---
name: enrich-job
description: Enrich job listings by visiting URLs in the local Chrome browser (CDP) and extracting structured data. Supports single-job and batch modes via scripts.
---

# enrich-job

Enrich jobs by navigating to each URL in the existing Chrome session (CDP) and extracting title, description, apply_url, salary_range, date_posted.

## CRITICAL: Visible Chrome

The enrichment script (`enrich_job.py`, line 79) opens a new CDP page. `page.bring_to_front()` MUST be called after `ctx.new_page()` so the user can watch. See the `job-pipeline` skill's `references/chrome-visibility.md` for the full pattern.

## Chrome pre-flight

```bash
curl -s http://localhost:9222/json/version | grep -q "{" && echo "OK" || echo "NOT_RUNNING"
```

If `NOT_RUNNING`: tell user to run `bash start-chrome.sh` first.

## Single job

```bash
python3 scripts/enrich_job.py --job-id <id>
```

## Batch — list of IDs

```bash
python3 scripts/enrich_jobs_batch.py --job-ids 42,43,44
# or space-separated:
python3 scripts/enrich_jobs_batch.py --job-ids 42 43 44
```

To enrich all `enrich_failed` jobs, first query the IDs:

```bash
python3 -c "
import sys; sys.path.insert(0, '.')
from scripts.db import get_connection
con = get_connection('jobs.db')
ids = [str(r['id']) for r in con.execute(\"SELECT id FROM jobs WHERE status='enrich_failed'\").fetchall()]
con.close()
print(','.join(ids))
"
```

Then pass the output to `--job-ids`.

## Failure modes

| Error | When |
|---|---|
| `extraction failed` | Description <100 chars after cleaning |
| Playwright timeout | Page didn't load in 20s |
| Any exception | Stored in `comment` column, status → `enrich_failed` |

## DB status after enrich

- Success → `status='new'`, fields written
- Failure → `status='enrich_failed'`, `comment` = error string
