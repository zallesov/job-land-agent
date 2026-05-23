---
name: run-scraping-pipeline
description: Run job scraping for one or all active providers. Reads config/user.yaml for providers, locations, search_terms. Triggered by "run scraping", "scrape jobs", "run wellfound", etc.
---

# Run Scraping Pipeline

## Trigger

- "run scraping" / "scrape jobs" → all active providers
- "run wellfound" → wellfound only
- "run greenhouse" / "run pipeline for greenhouse" → greenhouse only
- "run hirify" → hirify only

## Execution Rules

- Do NOT ask for confirmation to run the scrape. Execute immediately.
- On `AuthError`: stop that provider/location combo, tell user to run `/check-auth` first.
- On ingest failure (UNIQUE constraint, DB error): report the error and ask the user what to do. **Do not suggest or perform DB data deletion.**
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

If `NOT_RUNNING`: tell user to run `bash start-chrome.sh` first. Do not proceed.

**If Chrome is running but CDP is not responding** (`curl` returns empty): Chrome may be blocked by a macOS Keychain dialog (\"keychain cannot be found to store Chrome\"). Kill Chrome (`pkill -f \"Google Chrome\"`), verify `--use-mock-keychain` is in `start-chrome.sh`, and restart with `bash start-chrome.sh`. See `check-auth/references/chrome-profile.md` for details.

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
- Specific provider mentioned → use only that provider (must be present in config's `providers:` map and set to `true`; if missing entirely, see the "Provider not in config" pitfall below)
- "all" → use all active providers

## Step 4: Run each provider's scraper

```bash
# All providers use the unified pipeline (scrape → dedup → ingest → enrich → screen):
python3 scripts/scraping_pipeline.py --provider greenhouse
python3 scripts/scraping_pipeline.py --provider jobleads
python3 scripts/scraping_pipeline.py --provider wellfound
python3 scripts/scraping_pipeline.py --provider sprout
python3 scripts/scraping_pipeline.py --provider hirify
```

Skip inactive providers. Capture stdout. Parse log lines for counts.

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

Two failure modes:

1. **Feed empty** — The personalized "For You" feed at my.greenhouse.io is empty. If the user hasn't set job preferences (titles, locations, remote filter) on their Greenhouse profile, the feed returns nothing. Tell the user to go to https://my.greenhouse.io and configure their job preferences, then re-scrape.

2. **Cards found but "Profile filter: 0 relevant, 0 skipped"** — The scraper sees job cards on the page and counts them (e.g. "Found 11 cards"), but after filtering, both `relevant_rows` and `skip_rows` are empty. This means `collect_greenhouse()` returned rows where `url`, `title`, or `company` fields are empty/None — all three are required by the filter logic. The DOM extraction (`resultContainer()` and `textLines()` JS in `collect_greenhouse()`) likely broke due to a Greenhouse UI change. To debug, open my.greenhouse.io in Chrome, inspect card HTML structure. Fix the JavaScript extraction code in `scripts/providers/greenhouse/scrape_jobs.py`.

### JobLeads auth check may pass but scraping still fails

The `check_auth.py` script verifies the session cookie is present, but JobLeads has two silent-auth-failure modes that bypass the URL-based `is_auth_page()` check:

1. **Stale session** — the cookie exists but is expired. The scraper will exit with code 10 if the page redirects to a login URL.

2. **Anonymous mode** (MORE COMMON) — the session loads job search results normally, the page URL never shows a login wall, BUT every company name is hidden as "Solo para miembros registrados" and all salary data is generic. The scraper's `is_unauthenticated()` content-based check catches this by scanning for that exact phrase. Without this check, irrelevant jobs (Tax Advisor, sales roles, etc.) get scraped and ingested silently.

Both modes exit with code 10. Tell the user to log in at https://www.jobleads.com/login in Chrome, then re-scrape.

**Recovery after an unauthenticated scrape:** if bad jobs were already ingested, delete them before re-scraping:
```bash
python3 -c "import sqlite3; db=sqlite3.connect('jobs.db'); db.execute(\"DELETE FROM jobs WHERE provider='jobleads'\"); db.commit(); print(f'Deleted')"
```

### Provider not in config (not just disabled)

If a provider the user asks for isn't listed in `config/user.yaml`'s `providers:` section *at all*, the config-read step (`active_providers = [p for p, enabled in d['providers'].items() if enabled]`) won't find it. The scraper script may still exist and accept `--provider <name>`, but it won't be in the active list.

**Fix:** Add `provider_name: true` to the `providers:` section in `config/user.yaml`, then re-run.

### Hirify saved filters

Hirify does not use `search_terms`, `locations`, or `work_style` to build searches. The user must create saved filters on https://hirify.me/ first. The scraper opens every saved filter and collects all paginated jobs.

**Harmless warning noise:** The parser iterates filter indices and hits non-filter UI elements (notifications toggles, workflow preferences, etc.) at indices beyond the actual saved filters. Warnings like `Saved filter index not found: 29` through ~45 are normal and safe to ignore.

### Pipeline inline enrichment failures

`scripts/scraping_pipeline.py` runs enrichment inline as a post-ingest step via `scripts/pipeline/enrich_job.py`. When this step fails, jobs remain in the DB with `status='enrich_failed'` and the error string captured in the `comment` field.

**'AI Jobs' filter overlay:** Saved filters with combobox/dropdown UI can trigger an HTML overlay that intercepts Playwright clicks, causing a 30s timeout. The scraper continues with other filters — this is a partial-data loss, not a blocker. See `references/hirify-provider.md` for details.

### Wellfound scraping times out at larger scroll depths

Wellfound can display 350+ job cards and the scraper scrolls through all of them. At 20+ scroll pages the 300s default timeout may expire before scraping finishes, resulting in partial data (jobs already collected in earlier scrolls are still in the DB from prior runs, but no new jobs are ingested in the aborted run).

**Mitigation:** Either increase `timeout` to 600s in the `terminal()` call, or limit scroll depth in the scraper's Playwright code. The existing jobs in DB from previous successful runs are not affected.

### Sprout "Malaga" resolves to Malaga, WA Australia

Sprout's location autocomplete resolves "Malaga" to **Malaga, Western Australia** rather than Malaga, Spain. The scraper searches Malaga WA and finds Australian jobs (e.g. Peoplebank Australia, Canonical) which are irrelevant for a Spain-based search.

**Root cause:** Sprout uses Google Places Autocomplete and "Malaga" without a country qualifier matches the Australian suburb first. The fix is to either use a more specific location string in the config (e.g. "Malaga, Spain" instead of just "Malaga") or manually select the correct region on Sprout's location picker.

### Timeout risk with many provider × location combos

Running all combos in a single execute_code script will hit the 300s timeout when there are 6+ combos. For 4+ combos, run them as individual foreground `terminal()` calls (one per combo). For 8+ combos, consider using `terminal(background=true, notify_on_complete=true)` and polling with `process()`.

### Dedup uses `dedup_key`, DB uses UNIQUE on `url` — mismatch can crash ingest

`scripts/pipeline/dedup.py` checks for duplicate `dedup_key` values in the DB to decide which scraped jobs are "new." But `scripts/pipeline/ingest.py` has a `UNIQUE` constraint on the `url` column in the `jobs` table. If a job has the same URL as an existing job but a *different* `dedup_key` (e.g. because the key construction changed between scraper versions), dedup passes it as "new" but ingest crashes with:

```
sqlite3.IntegrityError: UNIQUE constraint failed: jobs.url
```

**No data is lost** — the crash happens before the INSERT, so DB contents are unchanged. But the pipeline exits with code 1 and no new jobs from that provider are ingested.

**Mitigation:** If this happens, report the crash and ask the user how they want to proceed. Never suggest or perform DB data deletion as a workaround.

### Never delete DB data without the user's explicit, unambiguously affirmative command

If scraping produces bad or overlapping data (wrong filters, corrupted auth, dedup mismatches), report the situation and ask "what should I do?" — do NOT offer "delete and re-scrape" as a choice in a clarify tool. The default response is to keep existing data as-is. Deletion is only appropriate when the user independently proposes it and states it clearly.

This rule is the user's expressed hard boundary — violating it erodes trust. It applies to ALL providers, not just wellfound.




### Sequential scraping is slow but reliable

Each provider/location combo takes 15–90 seconds. The pipeline scripts use the same Chrome instance (CDP port 9222), so running multiple simultaneously may cause contention. Prefer sequential execution unless the user specifically requests parallel.

### Do NOT reference `$HOME` or `Path.home()` in scripts

The agent's terminal environment resolves `$HOME` to `/Users/zall/.hermes/profiles/interviewprep/home` (Hermes sandbox), NOT `/Users/zall/`. Any script using `$HOME` or `Path.home()` for Chrome profile paths will silently create/write to the wrong directory, and Chrome will start with an empty profile.

**Fix:** Always use script-relative paths:
- Bash: `SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"` then `"$SCRIPT_DIR/.chrome-profile"`
- Python: `Path(__file__).resolve().parent.parent / ".chrome-profile"`

This also makes the project open-source friendly — no absolute paths, no environment assumptions.

See `check-auth/references/chrome-profile.md` for the full Chrome profile architecture.

## Examples

```
"run scraping"        → all active providers (locations read from config)
"run greenhouse"      → greenhouse scraper only
"run wellfound"       → wellfound scraper only
"run hirify"          → hirify saved filters only
```
