---
name: jobleads-daily-export
description: Use when updating the local append-only JobLeads jobs workbook from saved JobLeads searches, especially daily remote Spain/Berlin runs that must deduplicate by job URL and write provider-specific outputs under outputs/jobleads.
---

# JobLeads Daily Export

## Overview

Use this skill to scrape JobLeads search results and append new jobs to `/Users/zall/interviews/outputs/jobleads/jobs.xlsx`. The workbook is append-only at the row level: the job `url` is the deduplication key, existing rows are preserved unchanged, and only unseen URLs are appended.

Intermediate per-run JSON files are allowed and should be written under `/Users/zall/interviews/outputs/jobleads/runs/`.

## Workflow

1. Ensure output directories exist:

   ```bash
   mkdir -p /Users/zall/interviews/outputs/jobleads/runs
   ```

2. Use an authenticated browser session. Open one configured search URL first. If JobLeads redirects to `/external-home`, a login modal, or Google auth, ask the user to sign in in the Playwright browser profile, then retry.
3. Run the bundled Playwright MCP scrape script:

   ```bash
   cat /Users/zall/interviews/.codex/skills/jobleads-daily-export/scripts/scrape_jobleads_playwright_mcp.js
   ```

   Pass the complete file contents as `code` to `mcp__playwright__.browser_run_code_unsafe`. It saves a browser download to `/Users/zall/interviews/outputs/jobleads/runs/jobleads_jobs_live_YYYY-MM-DD.json`.
4. Confirm the scrape result reports nonzero `count`, expected `countries`, `missingDescriptions = 0`, and `missingPostingDates = 0`.
5. Append the fresh run to the provider workbook:

   ```bash
   python3 /Users/zall/interviews/.codex/skills/jobleads-daily-export/scripts/update_jobleads_workbook.py \
     --fresh-json /Users/zall/interviews/outputs/jobleads/runs/jobleads_jobs_live_YYYY-MM-DD.json \
     --xlsx /Users/zall/interviews/outputs/jobleads/jobs.xlsx \
     --state-json /Users/zall/interviews/outputs/jobleads/state.json \
     --today YYYY-MM-DD
   ```

6. Verify the XLSX and state JSON by reading them back before reporting completion.

## Deduplication

- URL is the only deduplication key.
- If a fresh row URL already exists in `jobs.xlsx`, do not update that row.
- Preserve existing `status`, `comment`, `first seen`, `last seen`, and all other existing cells.
- Do not mark missing jobs as removed. The workbook is append-only.
- Dedupe within the fresh run as well as against the existing workbook.

## Default Searches

Use these searches unless the user gives different URLs:

- Spain Remote 100k+: `https://www.jobleads.com/search/jobs?view=for-you&location_country=ES&filter_by_contractType=full_time&filter_by_remote=remote&minSalary=100000`
- Berlin Remote 100k+: `https://www.jobleads.com/search/jobs?view=for-you&location=Berlin%2C%20Germany&location_latitude=52.5173885&location_longitude=13.3951309&location_coordinates_radius=29495.470786527792&location_country=DE&filter_by_contractType=full_time&filter_by_remote=remote&minSalary=100000`

## Fields

Collect:

- provider: `jobleads`
- company
- title
- url
- description
- apply url, only if JobLeads exposes a separate external URL
- location
- country
- date of job posting
- first seen
- last seen

## Verification Commands

Validate the fresh JSON:

```bash
python3 -c 'import json; rows=json.load(open("/Users/zall/interviews/outputs/jobleads/runs/jobleads_jobs_live_YYYY-MM-DD.json")); print(json.dumps({"fresh_rows": len(rows), "unique_urls": len({r.get("url") for r in rows}), "countries": sorted({r.get("country") for r in rows}), "missing_descriptions": sum(1 for r in rows if not r.get("description")), "missing_posting_dates": sum(1 for r in rows if not r.get("postingDate"))}, indent=2))'
```

Read back the provider workbook:

```bash
python3 -c 'import importlib.util, json; p="/Users/zall/interviews/.codex/skills/jobleads-daily-export/scripts/update_jobleads_workbook.py"; s=importlib.util.spec_from_file_location("u", p); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); rows=m.read_xlsx(m.Path("/Users/zall/interviews/outputs/jobleads/jobs.xlsx")); print(json.dumps({"xlsx_rows": len(rows), "unique_urls": len({r.get("url") for r in rows}), "provider_rows": sum(1 for r in rows if r.get("provider") == "jobleads"), "missing_required_fields": sum(1 for r in rows if not all(r.get(k) for k in ["provider", "company", "title", "url", "description", "location", "country", "first seen", "last seen"]))}, indent=2))'
```
