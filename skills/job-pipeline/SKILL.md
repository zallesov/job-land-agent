---
name: job-pipeline
description: Run the job scraping pipeline for one or all providers. Knows the full pipeline internals for recovery. Triggered by "run scraping", "run wellfound", "run pipeline", "scrape jobs", etc.
---

# Job Pipeline

## Trigger

- "run scraping" / "scrape jobs" → all active providers
- "run wellfound" / "run greenhouse" / etc. → single provider
- "pipeline failed" / "enrich failed" / "jobs not screened" → recovery

---

## CRITICAL: Chrome Must Be VISIBLE

**The user watches the Chrome window.** Do NOT use `ctx.new_page()` without immediately calling `page.bring_to_front()` — the tab must appear and be focused in the user's Chrome window so they can watch the work happen.

Rule enforced in AGENTS.md (see "ALL CHROME OPERATIONS MUST BE VISIBLE"):
- After `page = ctx.new_page()`, call `page.bring_to_front()` before any `page.goto()` or navigation.
- No background/invisible tabs. Tabs close after extraction (fine), but the user saw them.
- Applies to: scraping scripts (`scrape_jobs.py`), enrichment scripts (`enrich_job.py`, `enrich_jobs_batch.py`), add-job-by-url, and any ad-hoc CDP page creation.
- Exception: only skip if the user explicitly asks for quiet/no-visual mode.

### How to check current scripts

```bash
grep -n 'new_page()' scripts/providers/*/scrape_jobs.py scripts/pipeline/enrich_job.py scripts/enrich_jobs_batch.py
```

If any `new_page()` call is NOT immediately followed by `bring_to_front()`, the script needs a fix. See `references/chrome-visibility.md`.

---

## How to Run

```bash
# Pre-flight: Chrome must be running
curl -s http://localhost:9222/json/version | grep -q "{" && echo "OK" || echo "NOT_RUNNING"
```

If `NOT_RUNNING`: tell user to run `bash start-chrome.sh`. Do not proceed.

```bash
# Run one provider
python3 scripts/scraping_pipeline.py --provider <name>

# Providers: greenhouse | jobleads | wellfound | sprout | hirify | csvfeed
```

Active providers read from `config/user.yaml` → `providers:`. Skip disabled ones.

Run providers sequentially — all share the same Chrome CDP port, parallel runs cause contention.

## Enrichment Timeout on Large Batches

The pipeline enriches jobs one-at-a-time via CDP. For a large batch (100+ jobs), the default 300s can timeout before all jobs are enriched — each page load + DOM extraction takes ~2–4s.

**Signs:** Pipeline output shows enrichment progress then `[Command timed out after 300s]`. Enriched jobs up to the timeout point are saved in the DB; rest remain `status='new'`.

**Fix after timeout:**
```bash
# Collect unenriched job IDs
JOB_IDS=$(sqlite3 jobs.db "SELECT id FROM jobs WHERE provider='<name>' AND status='new' ORDER BY id;" | tr '\n' ' ')
# Run enrichment separately
python3 scripts/enrich_jobs_batch.py --job-ids $JOB_IDS --workers 3
# Then screen. DEEPSEEK_API_KEY must already be exported in this shell.
JOB_IDS=$(sqlite3 jobs.db "SELECT id FROM jobs WHERE provider='<name>' AND status='enriched' AND length(description)>50 ORDER BY id;" | tr '\n' ' ')
```

If `batch_screen_jobs.py` is missing, use the underlying module directly:
```bash
python3 -c "
import sys; sys.path.insert(0, 'scripts')
from pipeline.screen_jobs_batch import screen_jobs_batch
import os
# export DEEPSEEK_API_KEY first
ok_ids, failures = screen_jobs_batch([LIST_OF_IDS], max_workers=5)
"

## User Login Flow (Pre-Pipeline)

When the user says "let me log in" or "I need to log in to X":
- Navigate the browser to the provider's login page immediately. Do NOT just confirm Chrome is running and tell the user to go there.
- The user wants you to open the tab. They'll type credentials themselves.
- Provider login URLs: Greenhouse → https://my.greenhouse.io/users/sign_in, JobLeads → https://www.jobleads.com/login, Wellfound → https://wellfound.com/login, Sprout → https://app.usesprout.com/login

---

## What the Pipeline Does (Under the Hood)

```
check_auth → scrape_jobs → dedup_jobs → ingest_jobs → enrich_job (per job) → screen_job (per job) → send_daily_digest
```

### 1. `check_auth`
`scripts/providers/<name>/check_auth.py` — navigates to the provider's jobs page in the existing Chrome, checks for login redirect. Raises `AuthError` if not authenticated. Pipeline stops that provider.

### 2. `scrape_jobs`
`scripts/providers/<name>/scrape_jobs.py` — Playwright `connect_over_cdp("localhost:9222")`. Attaches to existing Chrome session (cookies, sessions, bot-detection tokens all inherited). Returns `list[ShallowJob]`. All providers return `status="new"` — no filtering at scrape time.

### 3. `dedup_jobs`
`scripts/pipeline/dedup.py` — filters scraped jobs against DB by both `dedup_key` (`company::title`) and `url`. Also deduplicates within the incoming batch. Returns only genuinely new jobs.

### 4. `ingest_jobs`
`scripts/pipeline/ingest.py` — INSERTs new jobs to `jobs` table. Returns IDs of ingested jobs. All jobs land in DB; pipeline only proceeds with returned IDs.

### 5. `enrich_job`
`scripts/pipeline/enrich_job.py` — for each job ID: opens a new page in existing Chrome via CDP, navigates to job URL, extracts title / description / apply_url / salary_range / date_posted from DOM. Writes directly to DB. Sets `status='new'` on success, `status='enrich_failed'` on failure.

### 6. `screen_job`
`scripts/pipeline/screen_job.py` — Hermes `screen-job` skill call per job. Reads CV + job description, produces `apply_verdict` + `relevance_score`. Writes to `job_assessments`. Sets `status='screened'`.

### 7. `send_daily_digest`
### No success notification

`send_daily_digest()` only fires when there are failures (line 21-22: `if not enrich_failures and not screen_failures: return`). Successful pipeline runs produce NO Telegram notification. Batch screening via `pipeline.screen_jobs_batch` also produces no notification from the pipeline itself — but the individual `screen_job.py` now sends per-job Telegram notifications via `_notify_screened()`.

### `posted_company_name` may be empty

Jobs ingested from some sources (csvfeed with missing data, malformed scrapes) can have an empty `posted_company_name`. Searching by company name will miss them. Always use URL or id for reliable lookup:

```sql
SELECT id, title, url FROM jobs WHERE url LIKE '%frontcareers%';
-- or
SELECT id, title, posted_company_name FROM jobs WHERE id=2515;
```

When a user says "find job at company X" and no results match, check both the URL pattern AND do a broader search — the company field might be blank even though the URL clearly identifies the employer.

### Prefer existing pipeline scripts over ad-hoc wrappers

When the pipeline has a script for a job — `db_write_job_fields.py`, `db_write_research.py`, `pipeline.screen_jobs_batch`, `pipeline.screen_job`, `pipeline.ingest`, `pipeline.dedup`, `pipeline.enrich_job` — **use it directly**. Do NOT write wrapper scripts that call them from subprocess. The user will notice and correct you.

The correct pattern for a batch loop:

```bash
# Loop over job IDs directly, don't write a Python wrapper
for jid in $(sqlite3 jobs.db "SELECT id FROM jobs WHERE provider='csvfeed' AND status='enrich_failed'"); do
  python3 scripts/db_write_job_fields.py --db jobs.db --job-id $jid < tmp/fields_$jid.json
done
```

Or use the Python module directly in a single inline invocation (one-liner via `python3 -c "..."`) rather than a file-based script in `tmp/`.



## Per-Provider Notes

### Wellfound
- **CDP mandatory** — WellFound uses DataDome bot protection. Jina, curl, headless Playwright all get HTTP 403. Only CDP to existing Chrome works (rides on the already-passed DataDome cookie).
- Searches all `search_terms` from config in one shot via the role input field (comma-separated).
- Remote mode → single "Europe" location search. Non-remote → iterates cities from config.
- **Never click the Filters modal** — it resets SPA state and drops all job links to 0. Use the inline toggle buttons (Full Time, Remote) instead.
- Location change is best-effort — if the UI interaction fails, continues with saved search location (non-fatal).

### JobLeads
- **Two silent auth failure modes:**
  1. Redirect to login URL → script exits with code 10
  2. Anonymous mode — page loads normally but company names show as "Solo para miembros registrados". `_is_unauthenticated()` detects this via content scan, exits 10.
- Both modes: tell user to log in at jobleads.com in Chrome, then re-run.
- If bad jobs were ingested before detection: report to user, ask what to do. Never delete without explicit instruction.
- **Do NOT rely on URL params for search.** `https://www.jobleads.com/search/jobs?...` and `view=for-you` are not a durable search API. They can land on empty recommendation feeds even when matching jobs exist.
- **Correct scraping path:** open the plain jobs page (`https://www.jobleads.com/es/jobs` or the current locale's `/jobs` page), then drive the visible search UI:
  - select country from the country dropdown list
  - fill keyword/title
  - fill city/location
  - set Remote in the work-model dropdown when the user's work_style prefers remote
  - submit the form and scrape the resulting list page
- **Country dropdown pitfall:** if the desired country is already selected (for example Germany), skip the country-selection step entirely. Trying to re-select the already-active country can fail because the active country link is not meaningfully clickable in Playwright.
- **Use config search_terms, not an empty query.** For JobLeads, loop over `config/user.yaml` `search_terms` and run one in-page search per term; deduplicate results by URL across searches.
- **Selector/interaction pitfall:** the country chooser is not a normal editable select. The reliable pattern is to open the dropdown, type into the dropdown's own search input, then click the matching country entry from the rendered list. For some UI states, native Playwright `.click()` on the visible text can fail; a page-context `element.click()` on the matching country link is the fallback.
- **Verification step:** after form submission, confirm the page actually changed to a search-results URL and contains job links before declaring "0 jobs". If the page body still shows only the generic feed or an empty-state recommendation page, the search interaction did not complete correctly.
- See `references/jobleads-ui-search.md` for the concrete interaction pattern and failure modes.
- **Do NOT rely on URL query params to drive JobLeads search.** `https://www.jobleads.com/search/jobs?...` / `view=for-you` is not a reliable search surface and can land on a zero-results state even when the real search UI has jobs.
- Correct approach: open the plain jobs page (`https://www.jobleads.com/es/jobs` or the current locale equivalent), then fill the in-page controls: country, keyword, location, remote/work-model, then submit the form.
- **Country selector pitfall:** if the desired country is already active in the country dropdown, skip the country-selection step entirely. Attempting to re-select the already-active country can fail because the active option is not interactable in the same way as inactive options.
- For user-visible debugging, distinguish these cases clearly:
  - reached the page but got zero matches after applying filters
  - failed to drive the search UI / selectors changed
  - auth failed
- **Do NOT rely on URL params for search.** `https://www.jobleads.com/search/jobs?...` / `?view=for-you&...` is not the durable search flow here. Start from the plain jobs page (`https://www.jobleads.com/es/jobs` or the locale-specific equivalent), then drive the in-page search UI.
- **Search flow must be UI-driven:** select country in the country dropdown, fill keyword, fill location, set remote/work-model in the UI, then submit the form. Do not hallucinate that `location_country`, `filter_by_remote`, or similar query params are sufficient.
- **Country selection pitfall:** if the target country is already active, skip the country step. Re-selecting the already-active country can fail because the active link is hidden/detached after navigation. If country needs changing, typing into the country dropdown is only the filter step — you must click the actual country entry from the dropdown list.
- **Selector pitfall:** JobLeads UI language can switch between German and English mid-session. Prefer `data-testid` / structural selectors over visible text for core inputs and controls.
- **Search-page pitfall:** `https://www.jobleads.com/search/jobs` is not reliably controlled by query params alone. After login it may redirect to a localized results page like `/es/jobs?lastExecutedSearch=...`, and that redirected page can show real results even when the scraper's hardcoded `view=for-you&location_country=DE&filter_by_contractType=full_time&filter_by_remote=remote` URL returns `Für deine aktuellen Filter wurden keine Job-Matches gefunden`.
- When the scraper says `No job links found for Berlin Remote`, do not assume the site has no jobs. Verify the real browser destination and page text first. The durable lesson is: JobLeads may require driving the in-page search / saved-search workflow instead of relying on direct URL construction.
- See `references/jobleads-search-page.md`.

### Greenhouse
- Reads locations from `config/user.yaml` → `locations[]`, builds `for-you` feed URL per location.
- If "For You" feed returns 0 results: user needs to configure job preferences on my.greenhouse.io first.
- **Cards found but 0 extracted:** the card DOM structure changed and `collect_greenhouse()`'s `resultContainer()` function returned the wrong parent div. See `references/greenhouse-dom.md` for the full fix — the card's "View job" link innerText is just "View job", so title extraction relies on climbing to the correct card ancestor.

### Sprout
- Searches by title × location from config. Clicks each card → "View Original" → captures ATS URL.
- **React click pitfall**: Playwright `locator.click()` doesn't fire React handlers. Use `page.evaluate()` native `element.click()` for "View Original" button.
- **Stale pages**: prior browser tabs can break new-page detection. Provider closes all existing pages before starting.
- **Experience filter**: if Sprout's Filters dropdown has an experience level checked (e.g. "Executive"), only those roles show. Symptom: fewer cards than expected. Fix: manually uncheck in Chrome.
- **"Malaga" resolves to Australia**: Sprout's Google Places autocomplete resolves "Malaga" to Malaga, WA. Use "Malaga, Spain" in config if targeting Spain.

### Hirify
- Does NOT use `search_terms` or `locations` from config. Reads saved filters defined on hirify.me.
- User must create saved filters on hirify.me first.
- Iterates every saved filter, paginates through all results.

### csvfeed (file-based)
A local provider that reads jobs from a pre-filtered CSV file instead of scraping a real source.

**When to use:** User provides a spreadsheet/curated job list and wants it ingested into the pipeline without CDP scraping. Common trigger: Google Sheets export of a job board's Development/Engineering tab.

**Setup:**
1. Export Google Sheet to CSV: `curl -sL "https://docs.google.com/spreadsheets/d/<ID>/export?format=csv&gid=<GID>"`
2. Filter against user profile (seniority, location, role type, salary) into a second CSV
3. Create `scripts/providers/csvfeed/check_auth.py` — always returns True (no-op)
4. Create `scripts/providers/csvfeed/scrape_jobs.py` — reads filtered CSV, returns `list[ShallowJob]`
5. Register in `scraping_pipeline.py` by adding `"csvfeed"` to the `PROVIDERS` set

**Enrichment bypass:** csvfeed jobs already have descriptions from the CSV, but enrichment will fail if Chrome is down (it tries CDP). After ingest, use `db_write_job_fields.py` per job to write the CSV description to the DB, then reset status from `enrich_failed` to `new`:

```bash
python3 scripts/db_write_job_fields.py --db jobs.db --job-id <ID> < tmp/fields.json
python3 -c "from scripts.db import get_connection; con=get_connection('jobs.db'); con.execute(\"UPDATE jobs SET status='new', pipeline_status='new', updated_at=datetime('now') WHERE id=<ID>\"); con.commit(); con.close()"
```

Then run batch screening via `pipeline.screen_jobs_batch`.

**CRITICAL: after ingesting via pipeline, always run post-ingest enrichment separately** — the pipeline tries CDP enrichment per job (slow, 1-at-a-time) and will fail if Chrome is not running. See `references/csvfeed-provider-pattern.md`.

**Key constraint:** `ShallowJob` has no `description` field. Descriptions must be written post-ingest via `db_write_job_fields.py`. Do NOT write raw SQL to update descriptions — use the helper script.

---

## Recovery

### `enrich_failed` jobs

```sql
SELECT id, url, comment FROM jobs WHERE status='enrich_failed';
```

Re-run enrichment using the `enrich-job` skill (browser-based, CDP). Or reset and re-trigger:

```sql
UPDATE jobs SET status='new' WHERE status='enrich_failed';
```

Then run pipeline again — pipeline only enriches/screens jobs ingested in the current run, so reset jobs won't be picked up automatically. Use the `enrich-job` skill for batch recovery.

### Unscreened jobs

Pipeline screens only jobs ingested in the current run. Existing `new`/`enrich_failed` jobs are never revisited.

To screen existing jobs:
```sql
SELECT id FROM jobs WHERE status='new' AND description IS NOT NULL AND length(description) > 50;
```
Then call `screen-job` skill per job.

### AuthError

Provider's `check_auth` raised → Chrome session expired for that provider. Tell user to log in at the provider's site in Chrome, then re-run. Other providers continue normally.

### 0 new after dedup

Normal after the first run populates the DB. Means no new jobs scraped since last run.

### `screen_failed` jobs

Hermes `screen-job` call failed (Hermes not running, skill error). Jobs are in DB with descriptions. Use `screen-job` skill manually per job.

---

## DB Status Reference

See `references/db-maintenance.md` for deletion and maintenance workflows.

| status | meaning |
|---|---|
| `new` | ingested, not yet screened |
| `enrich_failed` | enrichment failed — no description |
| `screened` | screen-job completed, assessment in job_assessments |
| `researched` | full research done |
| `applied` | application submitted |
| `apply_failed` | application attempt failed |
