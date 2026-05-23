---
name: enrich-job
description: Enrich job listings by extracting structured data from URLs. Uses Jina AI Reader for batch, browser as fallback for JS-heavy pages. Supports single-job and bulk-DB modes.
---

# enrich-job

Enrich job listings by visiting URLs and extracting structured data (title, description, apply_url, salary_range, date_posted, location, remote_scope). Supports single-job and batch modes.

## Input

Single job:
`Use skill enrich-job. job_id: 42. url: https://boards.greenhouse.io/company/jobs/123.`

Batch (enrich all un-enriched jobs in DB):
`enrich all the jobs in the database`

## Extraction strategy

### Primary: Jina AI Reader
Fast, handles most ATS pages without JS overhead. Use for batch/bulk.

```
curl -sL --max-time 30 'https://r.jina.ai/<job_url>' -H 'Accept: text/plain'
```

Jina returns markdown with a `Title:` header line followed by page content.

### Fallback: Browser (native browser tools)
Use when Jina returns <100 chars or the title is just "Jobs" (Ashby blank page for removed listings). Navigate via `browser_navigate`, extract via `browser_snapshot` (full=true) and the accessibility tree.

Ashby pages that show "Job not found" heading are dead listings.

## Batch workflow

1. Query DB: `SELECT id, url FROM jobs WHERE description IS NULL OR trim(description) = '' AND status != 'deleted'`
2. Loop through URLs via `execute_code`, calling Jina for each (0.5s delay minimum)
3. Parse Jina output: extract title, description, salary, date_posted
4. For jobs where Jina fails (desc < 100 chars, title="Jobs"), fall back to browser
5. **Build and run SQL UPDATEs against `jobs.db`** using the exact patterns from the "How the calling layer writes to the database" section. Success: COALESCE for title/salary/date_posted, always overwrite description/apply_url, reset status to 'new'. Failure: set status='enrich_failed' with the error as comment. Every job gets a DB update.

## Title cleaning

Jina appends site boilerplate. Clean with:

```python
import re
def clean_title(t):
    if not t: return t
    # "Stellenangebot <title> bei <company>" -> extract title
    m = re.match(r'^Stellenangebot\s+(.+?)\s+bei\s+\S+', t)
    if m: t = m.group(1)
    # Remove " | Jobs at Company" suffix
    t = re.sub(r'\s*\|\s*Jobs at .+$', '', t)
    # Remove trailing " | Company"
    t = re.sub(r'\s*\|\s*\S+\s*$', '', t)
    return t.strip()
```

## Description cleaning

```python
import re
def clean_desc(content):
    desc = content
    desc = re.sub(r'Title:\s*.+?\n\n?', '', desc)  # strip Jina title prefix
    desc = re.sub(r'URL Source:\s*.+\n?', '', desc)
    desc = re.sub(r'Markdown Content:\s*', '', desc)
    desc = re.sub(r'\n{3,}', '\n\n', desc)
    return desc.strip()[:2000]  # cap at 2000 chars
```

## JSON parsing safety

Jina output may contain control characters. Parse with:

```python
with open("file.json", "r") as f:
    data = json.loads(f.read(), strict=False)
```

## Failure modes

| Error string | When to use |
|---|---|
| `broken url` | URL is a board/search page, not a specific job |
| `job expired` | Page explicitly says job expired |
| `job not found` | Ashby/ATS returns "Job not found" heading |
| `extraction failed` | Got content but <100 chars after cleaning |
| `login wall` | Page requires authentication |
| `page not found` | HTTP 404 |

## Output format

This skill is a pure extraction tool. It returns JSON. DB writes happen in the calling layer (script or chat agent). The canonical caller is `scripts/pipeline/enrich_job.py`.

### Success

```json
{"status": "success", "title": "Senior Backend Engineer", "description": "...", "apply_url": "https://...", "salary_range": "90-120K EUR", "date_posted": "2026-05-10"}
```

### Failure

```json
{"status": "failure", "error": "job not found"}
```

## How the calling layer writes to the database

This is the canonical DB update pattern, taken from `scripts/pipeline/enrich_job.py`. When invoked from chat (not via the script), the agent MUST replicate this exact logic.

### On success

`scripts/pipeline/enrich_job.py` does:

```python
con.execute(
    """UPDATE jobs SET title = COALESCE(?, title),
       description = ?, apply_url = ?,
       salary_range = COALESCE(?, salary_range),
       date_posted = COALESCE(?, date_posted),
       status = 'new', updated_at = datetime('now')
       WHERE id = ?""",
    (d.get("title"), d.get("description"), d.get("apply_url"),
     d.get("salary_range"), d.get("date_posted"), job_id),
)
```

Key points:
- `COALESCE(?, title)` for `title`, `salary_range`, `date_posted` — only overwrites if the new value is non-NULL
- `description` and `apply_url` are always overwritten (no COALESCE)
- `status` is reset to `'new'`
- `updated_at` is bumped

### On failure

`scripts/pipeline/enrich_job.py` calls `update_job_status(con, job_id, "enrich_failed", comment=result.error)` which is:

```python
con.execute(
    "UPDATE jobs SET status = ?, comment = ?, updated_at = datetime('now') WHERE id = ?",
    ("enrich_failed", error_string, job_id),
)
```

### Batch from chat: SQL template

When enriching from chat, build and run these directly:

```sql
-- Success:
UPDATE jobs SET 
  title = COALESCE('<title>', title),
  description = '<desc>',
  apply_url = '<url>',
  salary_range = COALESCE('<salary>', salary_range),
  date_posted = COALESCE('<date>', date_posted),
  status = 'new',
  updated_at = datetime('now')
WHERE id = <job_id>;

-- Failure:
UPDATE jobs SET 
  status = 'enrich_failed',
  comment = '<error reason>',
  updated_at = datetime('now')
WHERE id = <job_id>;
```

## Recovering from pipeline enrich failures

The pipeline's `scraping_pipeline.py` runs enrichment inline as a post-ingest step. When it fails (e.g. due to missing `run_agent` Hermes SDK), jobs are left in the DB with `status='enrich_failed'` and the error in the `comment` field. To recover:

1. Query the failed jobs:
   ```sql
   SELECT id, url, title FROM jobs WHERE status='enrich_failed';
   ```

2. Re-run enrichment via this skill (Jina/browser fallback) for each job, or use this SQL-safe pattern in batch mode:
   ```python
   db.execute("UPDATE jobs SET status='new' WHERE status='enrich_failed'")
   ```
   Then kick off the batch enrichment workflow below.

## Pitfalls

- **Jina rate limiting**: add 0.5s delay between batch calls
- **Ashby blank page = job removed**: Ashby shows sparse page (title="Jobs", few elements) for removed listings. Detect via `browser_snapshot` full=true looking for "Job not found" heading. Mark as `URL_ERROR: job not found on Ashby`.
- **Jina control characters in JSON**: use `strict=False` when parsing
- **Duplicate detection**: same URL with different query params (e.g. `?utm_source=Otta`) is the same job — the DB UNIQUE constraint on `url` may cause issues; strip query params before storing
- **Remote scope**: when location info is visible (e.g. "Berlin; Stockholm", "Hybrid"), populate both `location` and `remote_scope` columns
- **Pipeline enrichment vs manual enrichment are different code paths**: the pipeline's inline enrichment calls `scripts/pipeline/enrich_job.py` which uses `hermes_call()` (Hermes `run_agent` SDK). Manual enrichment using this skill uses Jina/browser. If the pipeline enrichment fails due to SDK issues, manual enrichment via this skill is a working workaround.
