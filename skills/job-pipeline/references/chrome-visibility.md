# Chrome Visibility Rules

## Why

Zall watches the Chrome window while the pipeline runs. Every CDP-created page must be visible and focused — no background tabs. `ctx.new_page()` via Playwright's `connect_over_cdp` creates a tab in the Chrome window, but it stays in the background (unfocused) unless `page.bring_to_front()` is called.

## Fix Pattern

Every `ctx.new_page()` must be followed by `page.bring_to_front()` before any navigation:

```python
# WRONG — invisible background tab
page = ctx.new_page()
page.goto(url)

# RIGHT — user sees the tab
page = ctx.new_page()
page.bring_to_front()
page.goto(url)
```

## Files to Fix

| File | Line | Code |
|---|---|---|
| `scripts/providers/wellfound/scrape_jobs.py` | 285 | `page = ctx.new_page()` |
| `scripts/pipeline/enrich_job.py` | 79 | `page = ctx.new_page()` |
| `scripts/enrich_jobs_batch.py` | (check) | `page = ctx.new_page()` |
| `scripts/add_job_by_url.py` | (check) | `page = ctx.new_page()` |
| Any other script using `connect_over_cdp` + `new_page()` | | |

## Verification

```bash
grep -n 'new_page()' scripts/providers/*/scrape_jobs.py scripts/pipeline/*.py scripts/*.py
```

Then check each is followed by `bring_to_front()` within 2 lines.

## Historical Context

Zall has mentioned this requirement repeatedly. It was documented in AGENTS.md under "ALL CHROME OPERATIONS MUST BE VISIBLE" during the session of 2026-05-23 after the wellfound pipeline run produced invisible background tabs that Zall couldn't observe.
