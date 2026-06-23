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

Then verify the Chrome process is using the active profile-local user-data-dir, not some other checkout's `.chrome-profile`:

```bash
ps -Ao pid,command | grep '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' | grep -- '--remote-debugging-port=9222' | grep -v grep
```

Expected for this profile:
- `--user-data-dir=/Users/zall/.hermes/profiles/joblandagent-dev/.chrome-profile`

If Chrome is listening on 9222 but the `--user-data-dir` points at a different checkout/profile (for example `/Users/zall/interviews/.chrome-profile`), stop and restart Chrome from the active profile root before trusting any auth or enrichment results.

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

To enrich all failed jobs, first query the IDs from PocketBase:

```bash
python3 -c "
import sys; sys.path.insert(0, '.')
from scripts.pb_client import get_pb
pb = get_pb()
ids = [str(j['id']) for j in pb.get_list('jobs', filter=\"pipeline_status='enrich_failed'\", sort='-created_at')]
print(','.join(ids))
"
```

Then pass the output to `--job-ids`.

## PocketBase-only note

Do not reintroduce `db_path` into the enrich helpers or wrappers. The batch and single-job enrich flows should talk to PocketBase directly for reads and writes.

## Failure modes

| Error | When |
|---|---|
| `extraction failed` | Description <100 chars after cleaning |
| `Browser.setDownloadBehavior: Browser context management is not supported` | Playwright `connect_over_cdp` can't manage contexts on this Chrome instance |
| Playwright timeout | Page didn't load in 20s |
| Any exception | Stored in `comment` column, status → `enrich_failed` |

### connect_over_cdp context management workaround

When enrich fails with `Browser.setDownloadBehavior: Browser context management is not supported`, Playwright's `connect_over_cdp` cannot manage the existing Chrome context. Use one of these alternatives:

**A. curl SSR extraction** (preferred — no browser needed): Many job boards serve full data as SSR HTML. Extract via curl and parse the JSON-LD or React hydration data embedded in the page. Write results via `db_write_job_fields.py`.

**B. `browser_cdp` tool** (fallback): Create a target page via CDP directly and use `Runtime.evaluate` to extract content. Avoids Playwright's context management entirely.

**C. `cdp_fallback.CdpPage`** (from hirify provider): A raw CDP-over-WebSocket implementation that sidesteps Playwright's context management entirely. Located in `scripts/providers/hirify/cdp_fallback.py`.

### Pre-check before enrichment

Before running enrichment, check if the page content is accessible via curl:
```bash
curl -sL --max-time 10 "<url>" | grep -oP '<script type="application/ld\+json">'
```
If JSON-LD or React hydration data is present, extract via curl — no browser needed.

### Verify Chrome launched from the active profile root

After restarting Chrome, inspect the running process and confirm `--user-data-dir` points at the active Hermes profile-local `.chrome-profile`, not a developer checkout or another repo root. A mismatched user-data-dir leaks state across profiles and can make browser results misleading even when CDP itself works.

### Site-specific extraction sanity checks

Some pages contain multiple `<h1>` elements. Do not trust a successful enrich blindly when the extracted title is a generic CTA like `Apply Now`. Impala Search is a known example: the sidebar apply form has an `<h1>` that appears before the real vacancy title. For this case, verify the title after enrichment and use the fallback extraction patterns in `references/impala-search.md` when needed.

### Impala Search company-name pitfall

Impala Search vacancy pages may expose the real role title, location, salary, and description while hiding the actual client name behind generic wording like `Our client is ...`. In that case, leave `posted_company_name` blank rather than inventing a company from thin air.

## DB status after enrich

- Success → `status='new'`, fields written
- Failure → `status='enrich_failed'`, `comment` = error string
