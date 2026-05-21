---
name: jobleads-scraper
description: Knows how to invoke the JobLeads scraper script via CDP connection to local Chrome. Use when running the jobleads scraping step of the daily pipeline.
---

# JobLeads Scraper (CDP via Local Chrome)

**HARD RULE:** All JobLeads scraping MUST use `pw.chromium.connect_over_cdp("http://localhost:9222")` to attach to the user's existing Chrome. This inherits the Chrome profile (cookies, auth tokens, session state). There is no `--headless` mode — it's deprecated and ignored.

## Script

```
cd /Users/zall/interviews && python3 scripts/scrape_jobleads.py
```

## Parameters

| Flag | Default | Description |
|------|---------|-------------|
| `--location <preset>` | required | `berlin` or `spain` |
| `--titles <t1> <t2> ...` | none | Job titles (one keyword search per title); omit for personalised "for-you" feed |
| `--cdp-url <url>` | `http://localhost:9222` | CDP endpoint |
| `--search-url <url>` | none | Raw search URL (can repeat; overrides --location + --titles) |
| `--country <str>` | — | Country label (with --search-url) |
| `--location-label <str>` | — | Filename label (with --search-url) |
| `--date <YYYY-MM-DD>` | today | Output filename date stamp |
| `--wait-auth` | off | Wait for manual login on auth page instead of failing |
| `--headless` | — | **[DEPRECATED]** Ignored — CDP uses existing Chrome |
| `--browser-profile` | — | **[DEPRECATED]** Ignored — CDP uses existing Chrome profile |

## Output

```
outputs/jobleads/runs/jobleads_jobs_live_<date>_<location_slug>.json
```

## Session Persistence

Chrome profile at `~/.interviews-browser-profile` stores all session state. The scraper connects to the already-running Chrome — no separate browser launch. Auth, cookies, and session tokens persist across runs automatically.

## Pre-Flight

Chrome must be running on `localhost:9222`:

```bash
curl -s http://localhost:9222/json/version || echo "NOT_RUNNING"
```

If not running: user runs `~/start-chrome.sh`.

## Example Invocations

```bash
# Keyword search per title (all merged into one file):
python3 scripts/scrape_jobleads.py \
  --location berlin \
  --titles "Software Engineer" "AI Engineer" "Engineering Manager"

# Personalised feed (no titles):
python3 scripts/scrape_jobleads.py --location berlin
```

## Success Check

Exit code 0. Stdout contains JSON with `count` > 0.

## Known Locations

| Preset   | Country | Filter |
|----------|---------|--------|
| `spain`  | Spain   | ES, remote, 100k+ |
| `berlin` | Germany | Berlin, remote, 100k+ |
