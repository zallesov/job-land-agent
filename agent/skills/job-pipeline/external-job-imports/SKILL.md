---
name: external-job-imports
description: Use when importing job listings from user-supplied external sources such as spreadsheets, CSV exports, or other tabular feeds into the job pipeline.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [jobs, pipeline, import, csv, spreadsheet, ingestion]
    related_skills: [job-pipeline, import-from-spreadsheet]
---

# External Job Imports

## Overview

Use this skill when a user provides a batch of jobs outside the normal scraping providers and wants them brought into the pipeline. The class is broader than a single Google Sheet: CSV exports, manually maintained spreadsheets, and other table-shaped feeds all follow the same pattern — inspect columns, filter against the candidate profile, ingest through a temporary feed adapter, backfill fields the shallow ingest path cannot carry, then run downstream screening.

## When to Use

- User shares a Google Sheet or CSV of job listings.
- User wants a one-off import from an external tabular source.
- Normal providers do not cover the source, but the data is already structured.

Do not use for:
- Single-job manual research or enrichment.
- Normal provider scraping runs that already have a dedicated source adapter.

## Workflow

### 1. Acquire and inspect the source

Export or download the sheet as CSV, save it under `tmp/`, and inspect the structure before writing any filtering logic.

Typical Google Sheets export pattern:

```bash
curl -sL "https://docs.google.com/spreadsheets/d/<ID>/export?format=csv&gid=<TAB_ID>" \
  -A "Mozilla/5.0 ..." -o tmp/source_jobs.csv
```

Checks to perform:
- Row count is plausible.
- Required columns exist or can be mapped.
- Title/company/location/url fields are present.
- Salary/date/description columns are identified if available.
- If the source has both a geography column (for example `Country`) and a work-mode column (for example `Workplace Type`), determine which one encodes eligibility. Do not assume `Remote` in work mode means worldwide or EU-eligible remote.

Common spreadsheet pitfall:
- Curated job sheets often mark almost every role `Remote` in a `Workplace Type` column while the real hiring constraint lives in `Country` (`Germany`, `Spain`, `Remote`, etc.).
- When the user asks for `Germany`, `Spain`, `Remote`, or `Europe`, filter on the geography/eligibility column first; treat work-mode as secondary metadata.
- `Country=Remote` usually means geography-open remote. `Workplace Type=Remote` can still mean remote-only-from-a-specific-country.

### 2. Apply candidate-profile filtering

Write a temporary filter script in `tmp/` for the specific source schema. Use the user's standing constraints to drop obviously bad matches before ingest.

Common exclusion classes:
- Junior / intern / graduate roles
- Non-target functions outside software engineering or the user's declared lane
- Geography restrictions the user has ruled out
- Compensation below threshold
- Stack exclusions the user has stated repeatedly

Important spreadsheet-filtering rule: when the source has both a geography column (for example `Country`) and a work-mode column (for example `Workplace Type`), treat them separately. Do NOT infer geographic eligibility from `Workplace Type=Remote`. Many sheets mark roles as remote while still restricting them to a specific country. If the user says "Germany / Spain / Remote" or asks for "European countries plus fully remote", filter primarily on the geography column values (for example `Country in {Germany, Spain, Remote, ...}`), not on the remote/workplace column alone.

The goal is a cleaned `tmp/filtered_*.csv` file ready for ingest.

Before any DB write, quantify the filter result and sanity-check broad predicates. In spreadsheet imports, a condition like `remote OR Germany OR Spain` can effectively collapse to `remote`, which may match nearly the whole tab. Always produce:
- total source row count
- filtered row count
- a country/location breakdown
- a human-readable preview list (title, company, country, URL)

If the result set is unexpectedly large, stop before ingestion and ask the user to choose the scope (for example: all remote matches vs only Germany/Spain vs a stricter profile-based subset). This matters because downstream screening writes to PocketBase and can trigger one notification per screened job.

### 3. Use a temporary feed adapter, not a permanent provider change

When the pipeline already has a generic CSV-backed adapter, prefer it for one-off imports. If you must enable a temporary provider, do so only for the run and remove it afterward. Do not leave one-off adapters permanently enabled in the normal provider set.

The imported record should at minimum populate the shallow fields used for dedup and downstream enrichment:
- url
- title
- company
- location / country
- salary_raw
- posting_date
- dedup_key

### 4. Run pipeline ingest

Run the normal ingest path for the temporary feed and observe whether enrichment succeeded or failed.

### 5. Backfill fields shallow ingest cannot carry

Many external-feed adapters only populate shallow metadata. If description or other rich fields were present in the source file but not stored during ingest, write them back post-ingest using an existing DB update utility rather than inventing permanent custom scripts.

After backfill, reset any jobs left in an enrichment-failed holding state if the data is now complete enough for downstream work.

### 6. Batch-screen once descriptions are present

Only run batch screening after descriptions and key metadata are populated. Otherwise the verdict quality collapses into heuristics.

## Source-specific subsection: spreadsheet / CSV imports

Spreadsheet imports are the most common subclass:
- Export the target tab to CSV.
- Derive `gid` from the URL for Google Sheets.
- Preserve a copy of the raw export before filtering.
- Keep the filter logic in `tmp/`, not as a committed permanent pipeline change.
- Inspect the sheet schema carefully before filtering on “remote”. Some curated sheets use a `Country` column with values like `Remote`, `Germany`, `Spain`, etc., while a separate `Workplace Type` column may say `Remote` for nearly every row. In that schema, `Workplace Type=Remote` does **not** mean worldwide remote — it can still be country-restricted remote. When the user asks for `Remote / Germany / Spain / Europe`, apply the filter to the geographic eligibility column (`Country`) unless they explicitly ask for workplace mode.
- When the sheet has both `Country` and `Workplace Type`, treat them as different signals. `Workplace Type=Remote` often only means remote-within-that-country. If the user asks for Germany/Spain/Europe/Remote eligibility, filter on the `Country` field first; only use `Workplace Type` as a secondary hint, not as proof that the role is location-agnostic.

## Common Pitfalls

1. **Leaving a temporary provider enabled.** One-off feed adapters should not remain in the committed/default provider set after the import.
2. **Skipping schema inspection.** Spreadsheet columns vary; never assume title/company/location headers.
3. **Running screening before descriptions exist.** Shallow ingest often omits rich text, which makes screening low quality.
4. **Forgetting dedup behavior.** Imported jobs can collapse against already-scraped jobs if the dedup key matches.
5. **Hard-coding source-specific logic into the permanent pipeline.** Prefer temporary scripts and existing utilities.

## Verification Checklist

- [ ] Raw source file saved under `tmp/`
- [ ] Filtered output produced and spot-checked
- [ ] Temporary provider/feed path used only for the import
- [ ] Imported jobs have IDs and expected shallow metadata
- [ ] Descriptions/backfilled fields written where needed
- [ ] Any temporary pipeline toggle reverted
- [ ] Screening run only after data completeness was restored
