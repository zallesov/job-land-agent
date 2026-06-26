# Wellfound troubleshooting / recovery

Symptom → cause → fix. All commands run from the profile root (scripts self-locate, so
`agent/scripts/...` also works from the repo).

## Got a login page (not the feed)
- Cause: session expired / not logged in.
- Fix: **wellfound-login** — `bash start-chrome.sh`, log in by hand in the window. Re-check
  with **wellfound-check-auth**.

## "Access is temporarily restricted" / DataDome iframe
- Cause: bot block. Usually the **headless** bundled browser was used (missing `--cdp 9222`)
  or the IP got rate-scored (rapid open/close).
- Fix: ensure every `agent-browser` call has `--cdp 9222`; run `agent-browser close --all`
  once to drop a stale daemon; slow down. On a server: needs headed Chrome under Xvfb +
  residential proxy — datacenter IP is blocked even with valid cookies.
- Headless never passes wellfound DataDome (tested: `--headless=new`, webdriver-hidden,
  UA-spoof, stealth-init all blocked). Use headed (local) or Xvfb-headed (server).

## Slider / "verify you are human" mid-enrich
- The enrich script detects this, **halts** (does not checkpoint the blocked job), brings
  the window on-screen at the blocking URL, exits code 2.
- Fix: solve the slider by hand, then re-run the same enrich command — it resumes from the
  checkpoint (done jobs skipped, blocked job retried with fresh clearance).

## Enrich died mid-batch
- Just re-run the same command. The JSONL checkpoint (`tmp/wellfound/enriched.jsonl`) makes
  it skip already-enriched jobs. `--no-resume` forces a clean re-run.

## Parsing suddenly returns 0 (or far too few) jobs
- Cause: Wellfound changed hashed CSS classes, or infinite-scroll did not trigger.
- Debug: open `/jobs`, confirm logged in (avatar). Check the row selector still matches:
  `agent-browser --cdp 9222 eval 'document.querySelectorAll(`[class*="styles_jobListingList__"] [class*="styles_component__Ey28k"]`).length'`
  If 0, inspect a job card's classes (`a[href*="/jobs/"]` → climb parents) and update the
  `[class*="styles_..."]` prefixes in `wellfound_scrape.sh`. If a few only and a big result
  count is shown, the scroll plateaued — scroll harder / wait longer (do NOT switch to GraphQL).

## MCP write blocked / field rejected
- Confirm `jobs_create`/`jobs_update` are exposed (tool list). If a field is rejected, use
  the field names the MCP schema accepts — see **jobland-field-mapping**. Never fall back to
  local DB writes / SQL.
- enriched count in JobLand not growing: the write is an **agent step after** the enrich
  script — the script never writes to the DB. You must iterate `enriched_new.json` and call
  MCP per job. See wellfound-enrich-jobs Step 3.

## Cross-provider dedup looks wrong
- Keys: `dedup_key="{company}::{title}"` (casefolded), normalized `apply_url`, normalized
  `url`. False merges usually mean company+title collide across genuinely different roles —
  narrow with `--by apply_url,url`. Missed dups usually mean `tracked.json` was incomplete —
  re-fetch tracked keys via MCP (`jobs_list`/`jobs_search`).

## Session transfer stopped working (server)
- `datadome`/`cf_clearance` are IP+UA bound. Re-export a fresh session locally
  (`agent-browser --cdp 9222 state save`), re-import with `load_session.py`, match
  `CHROME_UA`, and use a residential proxy on the server. See **transfer-browser-session**.
