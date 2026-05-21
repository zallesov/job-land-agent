---
name: greenhouse-daily-export
description: Use when updating the local append-only Greenhouse/MyGreenhouse jobs workbook from remote Software Engineer, AI Engineer, and Engineering Manager searches across Berlin and Spain, deduplicated by job URL and written under outputs/greenhouse.
---

# Greenhouse Daily Export

## Overview

Use this skill to scrape Greenhouse/MyGreenhouse search results and append new jobs to `/Users/zall/interviews/outputs/greenhouse/jobs.xlsx`. The workbook is append-only at the row level: the job `url` is the deduplication key, existing rows are preserved unchanged, and only unseen URLs are appended.

Intermediate per-run JSON files are allowed and should be written under `/Users/zall/interviews/outputs/greenhouse/runs/`.

## Workflow

1. Ensure output directories exist:

   ```bash
   mkdir -p /Users/zall/interviews/outputs/greenhouse/runs
   ```

2. Use an authenticated Greenhouse browser session. If the example search URL redirects to `/users/sign_in`, ask the user to sign in in the Playwright browser and retry.
3. Run the bundled Playwright MCP scrape script:

   ```bash
   cat /Users/zall/interviews/.codex/skills/greenhouse-daily-export/scripts/scrape_greenhouse_playwright_mcp.js
   ```

   Pass the complete file contents as `code` to `mcp__playwright__.browser_run_code_unsafe`. It saves a browser download to `/Users/zall/interviews/outputs/greenhouse/runs/greenhouse_jobs_live_YYYY-MM-DD.json`.
4. Confirm the scrape result reports nonzero `count`, expected `countries`, `missingTitles = 0`, and low or zero missing descriptions.
5. Append the fresh run to the provider workbook:

   ```bash
   python3 /Users/zall/interviews/.codex/skills/greenhouse-daily-export/scripts/update_greenhouse_workbook.py \
     --fresh-json /Users/zall/interviews/outputs/greenhouse/runs/greenhouse_jobs_live_YYYY-MM-DD.json \
     --xlsx /Users/zall/interviews/outputs/greenhouse/jobs.xlsx \
     --state-json /Users/zall/interviews/outputs/greenhouse/state.json \
     --today YYYY-MM-DD
   ```

6. Verify the XLSX and state JSON by reading them back before reporting completion.

## Configured Searches

Run all six permutations:

- Software Engineer, Berlin remote
- Software Engineer, Spain remote
- AI Engineer, Berlin remote
- AI Engineer, Spain remote
- Engineering Manager, Berlin remote
- Engineering Manager, Spain remote

Example Berlin search:

```text
https://my.greenhouse.io/jobs?query=AI%20Engineer&location=Berlin%2C%20Germany&lat=52.524932&lon=13.407032&location_type=locality&country_short_name=DE&state_short_name=BE&work_type[]=remote
```

## Deduplication

- URL is the only deduplication key.
- If a fresh row URL already exists in `jobs.xlsx`, do not update that row.
- Preserve existing `status`, `comment`, `first seen`, `last seen`, and all other existing cells.
- Do not mark missing jobs as removed. The workbook is append-only.
- Dedupe within the fresh run as well as against the existing workbook.

## Fields

Collect:

- provider: `greenhouse`
- company
- title
- url
- description
- apply url: use the job URL unless Greenhouse exposes a clearer external apply URL
- location
- country: `Germany` or `Spain`
- date of job posting, only if visible
- first seen
- last seen

## Browser Notes

- Greenhouse requires authentication in the tested Playwright profile. If the page redirects to `https://my.greenhouse.io/users/sign_in`, ask the user to authenticate in Playwright and retry.
- Do not submit applications or transmit personal data.
- Do not click final apply/submit controls. Opening job detail pages is allowed.
- The scraper writes via a browser download because this Playwright runner does not expose Node filesystem APIs directly.

## Verification Commands

Validate the fresh JSON:

```bash
python3 -c 'import json; rows=json.load(open("/Users/zall/interviews/outputs/greenhouse/runs/greenhouse_jobs_live_YYYY-MM-DD.json")); print(json.dumps({"fresh_rows": len(rows), "unique_urls": len({r.get("url") for r in rows}), "countries": sorted({r.get("country") for r in rows}), "missing_titles": sum(1 for r in rows if not r.get("title")), "missing_companies": sum(1 for r in rows if not r.get("company")), "missing_descriptions": sum(1 for r in rows if not r.get("description"))}, indent=2))'
```

Read back the provider workbook:

```bash
python3 -c 'import importlib.util, json; p="/Users/zall/interviews/.codex/skills/greenhouse-daily-export/scripts/update_greenhouse_workbook.py"; s=importlib.util.spec_from_file_location("u", p); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); rows=m.read_xlsx(m.Path("/Users/zall/interviews/outputs/greenhouse/jobs.xlsx")); print(json.dumps({"xlsx_rows": len(rows), "unique_urls": len({r.get("url") for r in rows}), "provider_rows": sum(1 for r in rows if r.get("provider") == "greenhouse"), "missing_required_fields": sum(1 for r in rows if not all(r.get(k) for k in ["provider", "company", "title", "url", "description", "location", "country", "first seen", "last seen"]))}, indent=2))'
```
