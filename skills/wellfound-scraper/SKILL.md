---
name: wellfound-scraper
description: Knows how to invoke the WellFound scraper script with CDP connection to local Chrome. Use when running the WellFound scraping step of the daily pipeline.
---

# WellFound Scraper (CDP via Local Chrome)

**HARD RULE:** All WellFound scraping MUST use `pw.chromium.connect_over_cdp("http://localhost:9222")` to attach to the user's existing Chrome. This inherits the Chrome profile (cookies, DataDome tokens, saved searches, login state). Plain headless Playwright and `curl` both trigger DataDome bot protection (HTTP 403). There is no `--headless` mode.

## Script

```
cd /Users/zall/interviews && python3 scripts/scraping_pipeline.py --provider wellfound
```

Locations, titles, and work style read from `config/user.yaml` automatically. The pipeline handles scrape → dedup → ingest → enrich → screen inline.

**Location logic (config-driven):** When `work_style.preferred` is `"remote"`, the scraper runs a single \"Europe\" search. When non-remote, it iterates cities from `config/user.yaml` → `locations[]`. Filters (Remote, Full-Time, $100k+ salary) are applied via URL params and UI toggles.

## How It Works (6 Phases)

1. **Connect** — `connect_over_cdp` to local Chrome, create fresh page
2. **Navigate** — `wellfound.com/jobs?role=<title>&salary_min=100000&remote=true`, one page per search term
3. **Filter** — apply Remote/Full-Time/Salary UI toggles (skipped if `--no-filters`). Falls back to URL params when toggle buttons are disabled (saved-search state).
4. **Set location** — for remote mode (config `work_style.preferred: remote`): \"Europe\". For non-remote: specific city from config. Uses text-match click on location pill. If location change fails, continues with existing saved-search location (non-fatal warning).
5. **Scroll** — infinite scroll to load all results (up to 25 iterations, stops after 4 stale scrolls). First search scrolls ~360 jobs; subsequent search terms typically find 0 new (dedup happens inline).
6. **Collect** — extract job cards from DOM via `page.evaluate`, dedup by URL across searches.
7. **Filter** — `is_relevant()` title-based filter separates jobs into relevant + skip lists.
8. **Enrich** — visit each relevant job's detail page for full description + skills + salary (skipped if `--skip-enrich`).

## Session Persistence Model (IMPORTANT)

The Chrome profile at `.chrome-profile/` (inside the project dir) stores ALL session state permanently:
- WellFound login (Google OAuth token)
- DataDome bot-detection cookie
- Saved search configuration (roles, location, filters)

**Pattern**: Update the saved search ONCE manually in the browser (add Remote Only, Salary $100k+, Full Time), then every future pipeline run inherits those filters automatically via the Chrome profile.

## Pre-Flight Checklist

1. **Chrome must be running**: `curl -s http://localhost:9222/json/version`
2. **Chrome must be authenticated** with WellFound (Google OAuth complete)
3. **Saved search must be configured** with desired filters

If Chrome not running: tell user to run `bash start-chrome.sh`.

## Google One Tap Auth Flow

First navigation to WellFound triggers Google OAuth redirect to `accounts.google.com/signin/oauth/id` (client_id for WellFound). Steps:
1. Page shows "Sign in with Google" with user's Google account
2. Click "Continue" on the OAuth consent screen ("You're signing back in to wellfound.com")
3. Lands on authenticated `/jobs` page with profile + saved searches

This flow happens once per Chrome profile lifetime. Subsequent runs skip it.

## Pitfalls

### 1. DataDome Bot Protection (CRITICAL)
WellFound uses DataDome. `curl` gets HTTP 403 with a `datadome=` cookie challenge. Plain headless Playwright also gets blocked. The CDP connection to existing Chrome is the ONLY approach that works — it rides on the already-passed DataDome challenge stored in Chrome's cookie jar.

### 2. Filters Modal Resets SPA State
Clicking the "Filters" button opens a modal that DESTROYS the current search state. After closing it, job links drop to 0. **Never click the Filters button in automated scripts.** Use simple toggle buttons in the search bar (Full Time, Remote) or URL parameters instead.

### 3. Remote Toggle Disabled with Saved Search
When a saved search is active, the Remote/On-site toggle button is `disabled`. The `apply_filters()` function detects this with `.is_enabled()` and falls back gracefully. For reliable filtering, update the saved search manually.

### 4. Browser Tool Tab Conflicts
When both `browser_navigate` (native tool) and Playwright MCP are connected to the same Chrome instance, they compete for tab focus. Pages navigate away unexpectedly. **Prefer the Python `connect_over_cdp` script for scraping** — it creates its own page in the context and doesn't interfere with existing tabs.

### 5. Playwright MCP `ERR_ABORTED` Workaround
If Playwright MCP returns `net::ERR_ABORTED` when navigating to WellFound, navigate to `about:blank` first, then to the target URL. This clears any stuck navigation state.

### 6. Location Change UI Fragility
The location change function tries multiple selectors (button with map-pin img, text match, combobox). WellFound's UI changes frequently. If it fails, the script continues with the saved search location — this is safe and expected. The warning `[WARN] Could not change location` is non-fatal.

### 7. Infinite Scroll Stop Criteria
Script stops after 4 consecutive scrolls with no new job links. WellFound typically loads all results in 15-20 scrolls. If total is unexpectedly low (<20), the saved search may be too restrictive.

### 8. `textbox` is not a Playwright locator
Playwright uses `input` or `[role="textbox"]`, not `textbox`. Using `textbox` causes `TimeoutError`. Use `input[placeholder="..."]` instead.

### 9. React SPAs may need JS click() instead of Playwright click()
When a button that should navigate or open a popup does nothing on `locator.click()`, try `page.evaluate()` with native `element.click()`. Playwright's synthetic click doesn't always trigger React event handlers. This applies to WellFound, Sprout, and any React-based ATS.

### 10. Enrichment failures leave missing descriptions — targeted retry

When enrichment fails (page load timeout, SPA navigation, ATS redirect), the job is still in the output file but with an empty `description` field. Running the full scraper again is wasteful (re-scrolls 360+ cards). Instead, use a targeted enrichment-only script that queries `jobs.db` for wellfound jobs with empty descriptions and visits only their URLs:

```bash
python3 tmp/enrich_missing_wellfound.py
```

This connects to the same CDP Chrome, visits each un-enriched URL, runs the same JS extraction as `enrich_wellfound_job()`, and updates `jobs.db` directly. It skips the scrape → scroll → collect phases entirely. Typically enriches 40-150 jobs in a single pass.

If enrichment fails in the script too (0 enriched / all failed), check the DB column name — the script uses `salary_range` (not `salary_raw`). The scraper's original enrichment writes to the in-memory dict; the retry script writes to the DB column directly.

## Playwright MCP (Alternative for Interactive Use)

For manual inspection or one-off searches, Playwright MCP wired to the same CDP endpoint works:

```yaml
# config.yaml
playwright:
  command: "npx"
  args:
    - "-y"
    - "@playwright/mcp"
    - "--cdp-endpoint"
    - "http://localhost:9222"
```

Key tools: `mcp_playwright_browser_navigate`, `mcp_playwright_browser_evaluate`, `mcp_playwright_browser_snapshot`, `mcp_playwright_browser_wait_for`.

Workaround for ERR_ABORTED: navigate to `about:blank` first, then target URL.

## Success Check

Exit code 0. Stdout contains JSON with `count` > 0. Output file is valid JSON array.

## Known Locations

For **remote** mode (`work_style.preferred: remote`): the scraper uses a single `"Europe"` search — no city-specific runs. All results are remote-first, Europe-filtered. This avoids the location-change fragility (WellFound's location pill is unreliable to programmatically click).

For **non-remote** mode: iterates configured cities from `config/user.yaml`.

| Mode     | Search Query       |
|----------|--------------------|
| remote   | Europe             |
| non-remote | Berlin, Germany  |
| non-remote | Spain            |
