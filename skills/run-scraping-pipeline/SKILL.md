---
name: run-scraping-pipeline
description: Run job scraping for one or all active providers. Reads config/user.yaml for providers, locations, search_terms. Triggered by "run scraping", "scrape jobs", "run wellfound", etc.
---

# Run Scraping Pipeline

## Trigger

- "run scraping" / "scrape jobs" → all active providers
- "run wellfound" → wellfound only
- "run greenhouse" / "run pipeline for greenhouse" → greenhouse only

## Execution Rules

- Do NOT ask for confirmation. Execute immediately.
- On `AuthError`: stop that provider/location combo, tell user to run `/check-auth` first.
- Report per run: scraped count / new after dedup / ingested / failures.

## Step 0: Prerequisites

Ensure `pyyaml` is installed:

```bash
python3 -c "import yaml" 2>/dev/null || pip3 install pyyaml
```

## Step 1: Chrome pre-flight check

```bash
curl -s http://localhost:9222/json/version 2>&1 | head -1 | grep -q "{" && echo "OK" || echo "NOT_RUNNING"
```

If `NOT_RUNNING`: tell user to run `~/start-chrome.sh` first. Do not proceed.

## Step 2: Read config

```bash
python3 -c "
import yaml, json
d = yaml.safe_load(open('config/user.yaml'))
active_providers = [p for p, enabled in d['providers'].items() if enabled]
locations = [loc['city'] for loc in d['locations']]
print(json.dumps({'providers': active_providers, 'locations': locations}))
"
```

## Step 3: Determine scope

Apply any overrides from the user's request:
- Specific provider mentioned → use only that provider (if active)
- "all" → use all active providers

## Step 4: Run each provider's scraper, then ingest

```bash
# For each active provider, run its scraper (reads config automatically):
python3 scripts/scrape_greenhouse.py
python3 scripts/scrape_jobleads.py
python3 scripts/scrape_wellfound.py
python3 scripts/scrape_sprout.py

# After all scrapers finish, ingest all outputs:
python3 scripts/ingest_provider_outputs.py --db jobs.db --all-latest
```

Skip scraper scripts for inactive providers. Capture stdout. Parse log lines for counts.

## Step 5: Report results

After all runs complete, summarize:

```
Scraping complete:
  greenhouse × Berlin: 42 scraped, 8 new, 8 ingested (0 enrich failures)
  jobleads × Berlin: 17 scraped, 3 new, 3 ingested (1 enrich failure)
  ...
Total: N new jobs added. Dashboard: http://localhost:3000
```

## Pitfalls & Known Issues

### Greenhouse "For You" feed returns 0 jobs

The Greenhouse scraper reads from the personalized "For You" feed at my.greenhouse.io. If the user hasn't set job preferences (titles, locations, remote filter) on their Greenhouse profile, the feed will be empty and the scraper will return 0 jobs. Tell the user to go to https://my.greenhouse.io and configure their job preferences, then re-scrape.

### JobLeads auth check may pass but scraping still fails

The `check_auth.py` script verifies the session cookie is present, but JobLeads has two silent-auth-failure modes that bypass the URL-based `is_auth_page()` check:

1. **Stale session** — the cookie exists but is expired. The scraper will exit with code 10 if the page redirects to a login URL.

2. **Anonymous mode** (MORE COMMON) — the session loads job search results normally, the page URL never shows a login wall, BUT every company name is hidden as "Solo para miembros registrados" and all salary data is generic. The scraper's `is_unauthenticated()` content-based check catches this by scanning for that exact phrase. Without this check, irrelevant jobs (Tax Advisor, sales roles, etc.) get scraped and ingested silently.

Both modes exit with code 10. Tell the user to log in at https://www.jobleads.com/login in Chrome, then re-scrape.

**Recovery after an unauthenticated scrape:** if bad jobs were already ingested, delete them before re-scraping:
```bash
python3 -c "import sqlite3; db=sqlite3.connect('jobs.db'); db.execute(\"DELETE FROM jobs WHERE provider='jobleads'\"); db.commit(); print(f'Deleted')"
```

### Timeout risk with many provider × location combos

Running all combos in a single execute_code script will hit the 300s timeout when there are 6+ combos. For 4+ combos, run them as individual foreground `terminal()` calls (one per combo). For 8+ combos, consider using `terminal(background=true, notify_on_complete=true)` and polling with `process()`.

### Ingest script has no `--provider` flag — use `--run-file` for single-provider ingest

The `ingest_provider_outputs.py` script does not support `--provider <name>`. When scraping a single provider, avoid `--all-latest` (which ingests ALL providers' latest output files, including stale runs from other providers). Instead, pass the specific output files:

```bash
python3 scripts/ingest_provider_outputs.py --db jobs.db \
  --run-file outputs/greenhouse/runs/greenhouse_jobs_live_<date>_berlin.json \
  --run-file outputs/greenhouse/runs/greenhouse_jobs_live_<date>_spain.json
```

Note: the script only accepts ONE `--run-file` per invocation. Run it once per output file if you have multiple location files for the same provider. The second run will update the already-inserted rows rather than creating duplicates.

### Sequential scraping is slow but reliable

Each provider/location combo takes 15–90 seconds. The pipeline scripts use the same Chrome instance (CDP port 9222), so running multiple simultaneously may cause contention. Prefer sequential execution unless the user specifically requests parallel.

## Examples

```
"run scraping"        → all active providers (locations read from config)
"run greenhouse"      → greenhouse scraper only
"run wellfound"       → wellfound scraper only
```
