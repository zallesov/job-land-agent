---
name: job-scraping-pipeline
description: Orchestrates the full daily job scraping pipeline. Reads config/pipeline_config.json, runs all scraper permutations, consolidates, ingests into SQLite, tags new jobs, and sends Telegram digest. Use this skill when running the daily pipeline cron job.
---

# Daily Job Scraping Pipeline

## Work Directory

`/Users/zall/interviews`

## Overview

Read `config/pipeline_config.json`. For each source, run its scraper script for every permutation of locations × titles. Collect results, handle failures without aborting. After all scrapers finish, consolidate + ingest + tag + notify.

---

## Step 1: Read pipeline config

```bash
cat config/pipeline_config.json
```

Parse the `sources` array. Each source has:
- `name` — provider identifier
- `script` — path to scraper script
- `locations` — list of location presets
- `titles` — list of job title strings (empty = no title param)

---

## Step 2: Run all scraper permutations

For each source in `sources`:

- If `titles` is non-empty: run once per `(location, title)` pair
- If `titles` is empty: run once per `location`

Command pattern:

```bash
# With titles (e.g. greenhouse):
python3 <script> --location <location> --titles "<title>" --headless

# Without titles (e.g. jobleads):
python3 <script> --location <location> --headless
```

Run permutations **sequentially** (one at a time — browser profile can't handle parallel).

On failure of any single permutation:
- Log the error
- Continue to next permutation
- Track which permutations failed

---

## Step 3: Consolidate per provider

After all scrapers finish, for each source that had at least one successful run:

```bash
python3 scripts/consolidate_provider_run.py --provider <source_name>
```

This merges all `outputs/<provider>/runs/<provider>_jobs_live_<date>_*.json`
into `outputs/<provider>/runs/<provider>_jobs_live_<date>.json`.

---

## Step 4: Ingest into SQLite

```bash
python3 scripts/ingest_provider_outputs.py --db jobs.db --all-latest
```

---

## Step 5: Tag new jobs

```bash
python3 scripts/tag_new_jobs.py --db jobs.db
```

---

## Step 6: Send Telegram digest

```bash
python3 scripts/telegram_notify.py --type daily_digest --db jobs.db
```

If any permutations failed, also send failure alerts:

```bash
python3 scripts/telegram_notify.py \
  --type pipeline_failure \
  --provider <provider> \
  --step scrape \
  --error "<short error>" \
  --artifact-path "outputs/<provider>/runs/"
```

---

## Error Handling Rules

| Failure                  | Action                                      |
|--------------------------|---------------------------------------------|
| Single scraper permutation | Log + continue to next permutation        |
| All permutations for source | Log + skip consolidation for that source |
| Consolidation failure    | Log + skip ingestion for that source        |
| Ingest failure           | Send pipeline_failure alert, stop           |
| Tag failure              | Log, continue to digest                     |
| Telegram failure         | Log only                                    |

---

## Adding New Sources

Add an entry to `config/pipeline_config.json` and create a corresponding skill + script.
The pipeline will pick it up automatically on the next run.
