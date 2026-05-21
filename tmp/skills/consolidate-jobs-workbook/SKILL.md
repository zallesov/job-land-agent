---
name: consolidate-jobs-workbook
description: Use when consolidating provider job workbooks from outputs/jobleads/jobs.xlsx, outputs/greenhouse/jobs.xlsx, or other provider jobs.xlsx files into the local append-only ./jobs_all.xlsx while preserving existing comments, statuses, current interview fields, and old rows.
---

# Consolidate Jobs Workbook

## Overview

Use this skill to consolidate provider-specific job workbooks into `/Users/zall/interviews/jobs_all.xlsx`. The consolidated workbook is append-only at the row level: `url` is the deduplication key, existing rows are preserved, and only new URLs are appended.

This skill must not delete old rows or overwrite user-maintained fields such as `comment`, `status`, or `current interview status`.

## Workflow

1. Ensure provider workbooks exist, normally:

   ```bash
   ls -lh /Users/zall/interviews/outputs/jobleads/jobs.xlsx /Users/zall/interviews/outputs/greenhouse/jobs.xlsx
   ```

2. Run the bundled consolidator from `/Users/zall/interviews`:

   ```bash
   python3 /Users/zall/interviews/.codex/skills/consolidate-jobs-workbook/scripts/consolidate_jobs_workbook.py \
     --provider-xlsx /Users/zall/interviews/outputs/jobleads/jobs.xlsx \
     --provider-xlsx /Users/zall/interviews/outputs/greenhouse/jobs.xlsx \
     --output /Users/zall/interviews/jobs_all.xlsx \
     --today YYYY-MM-DD
   ```

3. Read back `jobs_all.xlsx` and verify:
   - row count is at least the prior row count
   - `final_rows == final_unique_urls`
   - new provider URLs are appended
   - existing rows with comments/statuses/current interview fields still exist

## Deduplication

- URL is the only deduplication key.
- If a provider row URL already exists in `jobs_all.xlsx`, skip it entirely.
- Do not update or overwrite existing rows.
- Do not delete rows that no longer appear in provider workbooks.
- Preserve all existing columns in `jobs_all.xlsx`.
- If provider columns are missing from `jobs_all.xlsx`, append the missing columns to the header row.

## Preservation Rules

- Preserve `comment`, `status`, `current interview status`, and any other user-created columns.
- Preserve existing row values exactly as read.
- When `jobs_all.xlsx` already exists, the script edits the existing worksheet XML and appends rows instead of rebuilding the whole workbook from scratch.
- The script creates a timestamped backup of `jobs_all.xlsx` before editing unless `--no-backup` is passed.
- Do not pass `--no-backup` unless the user explicitly asks to skip backups.

## Default Inputs

If no `--provider-xlsx` values are passed, the script defaults to:

- `/Users/zall/interviews/outputs/jobleads/jobs.xlsx`
- `/Users/zall/interviews/outputs/greenhouse/jobs.xlsx`

## Verification Commands

Read back the consolidated workbook:

```bash
python3 -c 'import importlib.util, json; p="/Users/zall/interviews/.codex/skills/consolidate-jobs-workbook/scripts/consolidate_jobs_workbook.py"; s=importlib.util.spec_from_file_location("u", p); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); rows=m.read_xlsx(m.Path("/Users/zall/interviews/jobs_all.xlsx")); print(json.dumps({"rows": len(rows), "unique_urls": len({r.get("url") for r in rows if r.get("url")}), "providers": sorted({r.get("provider") for r in rows if r.get("provider")}), "with_comment": sum(1 for r in rows if r.get("comment")), "with_status": sum(1 for r in rows if r.get("status")), "with_current_interview_status": sum(1 for r in rows if r.get("current interview status"))}, indent=2))'
```
