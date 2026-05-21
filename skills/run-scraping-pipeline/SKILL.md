---
name: run-scraping-pipeline
description: Run job scraping for one or all active providers × one or all configured locations. Reads config/user.yaml for providers, locations, search_terms. Triggered by "run scraping", "scrape jobs", "run pipeline for greenhouse berlin", etc.
---

# Run Scraping Pipeline

## Trigger

- "run scraping" / "scrape jobs" → all active providers × all locations
- "run greenhouse berlin" / "run pipeline for greenhouse berlin" → greenhouse × berlin only
- "run all scrapers for spain" / "scrape jobs in spain" → all active providers × spain
- "run wellfound" → wellfound × all locations

## Execution Rules

- Do NOT ask for confirmation. Execute immediately.
- On `AuthError`: stop that provider/location combo, tell user to run `/check-auth` first.
- Report per run: scraped count / new after dedup / ingested / failures.

## Step 1: Chrome pre-flight check

```bash
curl -s http://localhost:9222/json/version | python3 -c "import sys,json; d=json.load(sys.stdin); print('OK')" 2>/dev/null || echo "NOT_RUNNING"
```

If `NOT_RUNNING`: tell user to run `~/start-chrome.sh` first. Do not proceed.

## Step 2: Read config

```bash
python3 -c "
import yaml, json
d = yaml.safe_load(open('config/user.yaml'))
active_providers = [p for p, enabled in d['providers'].items() if enabled]
locations = [loc['city'] for loc in d['locations']]
titles = ','.join(d.get('search_terms', []))
print(json.dumps({'providers': active_providers, 'locations': locations, 'titles': titles}))
"
```

## Step 3: Determine scope

Apply any overrides from the user's request:
- Specific provider mentioned → use only that provider (if active)
- Specific location/city mentioned → use only that location
- "all" → use all active providers × all locations

## Step 4: Run pipeline for each (provider, location) combination

For each combination:

```bash
python3 scripts/scraping_pipeline.py \
  --provider <provider> \
  --location <city> \
  --titles "<comma-separated search_terms>"
```

Capture stdout. Parse `[pipeline]` log lines for counts.

## Step 5: Report results

After all runs complete, summarize:

```
Scraping complete:
  greenhouse × Berlin: 42 scraped, 8 new, 8 ingested (0 enrich failures)
  jobleads × Berlin: 17 scraped, 3 new, 3 ingested (1 enrich failure)
  ...
Total: N new jobs added. Dashboard: http://localhost:3000
```

## On AuthError

If a run exits with `AuthError`:

> Session expired for <provider>. Run `/check-auth` to verify and re-login, then try scraping again.

Stop that provider's runs but continue with others.

## Examples

```
"run scraping"                → all active providers × all configured locations
"run greenhouse berlin"       → greenhouse × Berlin only
"run all scrapers for spain"  → all active providers × Spain
"run wellfound"               → wellfound × all configured locations
```
