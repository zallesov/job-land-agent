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

- If `titles` is non-empty: run **once per location** passing ALL titles in a single invocation (both greenhouse and jobleads scripts accept `--titles` with `nargs="+"` and deduplicate internally, writing one output file per location)
- If `titles` is empty: run once per `location`

Command pattern:

```bash
# With titles — pass ALL titles in one call per location:
python3 <script> --location <location> --titles "Software Engineer" "AI Engineer" "Engineering Manager"

# Without titles (e.g. personalised feed):
python3 <script> --location <location>
```

Note: ALL scrapers now use CDP connection to local Chrome (no `--headless` flag anywhere). They require Chrome running on `localhost:9222`. Each scraper script has `--cdp-url` defaulting to `http://localhost:9222`.

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

**⚠️ Pitfall**: `find_latest_run_files()` sorts files alphabetically descending and picks the first. This means `_spain.json` or `_berlin.json` (partial location files) sort AFTER the consolidated file and can be misselected. If `--all-latest` only processes partial files, fall back to explicit `--run-file` pointing at the consolidated file:

```bash
python3 scripts/ingest_provider_outputs.py --db jobs.db \
  --run-file outputs/greenhouse/runs/greenhouse_jobs_live_$(date +%F).json
python3 scripts/ingest_provider_outputs.py --db jobs.db \
  --run-file outputs/jobleads/runs/jobleads_jobs_live_$(date +%F).json
```

**Verification**: After ingestion, check output for `inserted` + `updated` counts. The consolidated file should show both inserted (new URLs) and updated (known URLs with refreshed fields). If only partial location files were processed, you'll miss jobs from other locations.

---

## Step 5: Create kanban research tasks for new jobs

After every ingest run, new jobs with `status='new'` need research tasks. This runs for ALL providers — not just WellFound.

```bash
python3 scripts/list_new_jobs.py --db jobs.db
```

Parse the JSON. For each provider with `count > 0`, create ONE kanban task per provider via CLI:

```bash
hermes kanban create "research: <count> new <provider> jobs" \
  --body "Research <N> new <provider> jobs from pipeline. Use job-research skill. Samples: <top 5 from JSON output>" \
  --assignee interviewprep
```

**One task per provider, not one per job.** The research worker fans out internally.

If no new jobs, skip.

---

## Step 6: Tag new jobs

```bash
python3 scripts/tag_new_jobs.py --db jobs.db
```

---

## Step 7: Send Telegram digest

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
| **Exit code 10 (auth required)** | **⚠️ PAUSE PIPELINE.** Auth needed for this provider. Pause the cron job, notify user to sign in (`hermes cron pause 90b04916daed`). Do NOT continue to next permutation — user needs to log in. |
| Single scraper permutation | Log + continue to next permutation        |
| All permutations for source | Log + skip consolidation for that source |
| Consolidation failure    | Log + skip ingestion for that source        |
| Ingest failure           | Send pipeline_failure alert, stop           |
| Tag failure              | Log, continue to digest                     |
| Telegram failure         | Log only                                    |

---

## Pitfalls

| Pitfall | Symptom | Fix |
|---------|---------|-----|
| **New provider not in consolidate whitelist** | `consolidate_provider_run.py: error: argument --provider: invalid choice` | Edit `scripts/consolidate_provider_run.py` and add the provider to the `choices=[...]` list in `add_argument(\"--provider\")`. Every new pipeline source must be added here. |
| **`--all-latest` picks partial file** | `ingest_provider_outputs.py --all-latest` shows only one location's data (e.g. only `_spain` when `_berlin` also exists) | Use explicit `--run-file` pointing at the consolidated JSON, or patch `find_latest_run_files()` to prefer consolidated files over location-suffixed partials |
| **CDP connection fails** | `Could not connect to Chrome` or `No browser contexts found` | Chrome must be running on `localhost:9222`. User runs `~/start-chrome.sh`. All scrapers now use `connect_over_cdp` — no separate profile needed. |
| **Script exits 1 on auth failure** | `No job links found` or login page shows | Chrome profile at `~/.interviews-browser-profile` needs re-authentication. Open WellFound/Greenhouse/JobLeads in Chrome manually and sign in once. |
| **Playwright not installed** | `ModuleNotFoundError: No module named 'playwright'` | `pip3 install playwright` (`python3 -m playwright install chromium` no longer needed — CDP uses system Chrome) |
| **JobLeads spain yields 0 jobs** | `count: 0` — no error, just no listings | This is normal; Spain consistently has fewer/fewer-relevant postings. The consolidated file will have 0 rows from that partial |
| **Subagents timeout on batch company scraping** | `delegate_task` with 5+ companies per subagent hits 600s timeout | Use direct ATS API calls (not subagents) for batch checking. See `references/ats-direct-api.md` for curl patterns. Per-subagent scope: 1 company max |
| **Explee "Remote Teams" filter unreliable** | Companies tagged remote-first post hybrid/onsite roles (H Company, FlexAI, Peak) | Always verify per-role via actual ATS API. See `references/explee-company-discovery.md` |
| **Headful browser not available for Explee sign-in** | User asks to sign into Explee but no visible browser appears | agent-browser runs headless locally. Visible Chrome only via Playwright headed scripts. Guide user to sign in manually in their own browser; the headless browser shares the profile at `~/.interviews-browser-profile` |
| **WellFound needs CDP + live Chrome** | Playwright MCP returns `ERR_ABORTED`, or standalone Playwright gets DataDome 403 | Use `python3 scripts/scrape_wellfound.py` which runs `connect_over_cdp("http://localhost:9222")`. Chrome must be running (`~/start-chrome.sh`). See `wellfound-scraper` skill for session persistence, filter pitfalls, and infinite scroll patterns. |
| **Browser tool tab conflicts** | Pages navigate to random URLs, snapshots show wrong content | When both `browser_navigate` and Playwright MCP share the same Chrome, they fight over tabs. Use only ONE browser tool at a time, or use the Python CDP script instead. |

## Reference Docs

- `references/ats-direct-api.md` — Direct API access patterns for Greenhouse, Ashby, Lever (5-10x faster than browser)
- `references/explee-company-discovery.md` — Explee search strategies, filter pitfalls, batch-checking workflow
- `references/sprout-discovery.md` — Sprout platform architecture, search results, scraper plan (discovered, not yet built)
- `references/cdp-migration.md` — CDP migration pattern for all scrapers (connect_over_cdp, deprecated flags, pre-flight)
- `scripts/list_new_jobs.py` — Lists new jobs per provider for kanban research task creation

## Adding New Sources

Add an entry to `config/pipeline_config.json` and create a corresponding skill + script.
The pipeline will pick it up automatically on the next run.
