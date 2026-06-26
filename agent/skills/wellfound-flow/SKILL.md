---
name: wellfound-flow
description: Use to run the end-to-end Wellfound job pipeline — auth check, scrape, dedup, ingest, parallel enrich, then screen. A resumable, DB-status-driven sequencer that stops and waits for a human on any unclear situation.
---

# Wellfound Flow

End-to-end pipeline for the Wellfound provider. This skill is a **dumb sequencer**: it runs
the steps below in order, checks each step's exit code, and on **anything non-clean it
STOPS and waits for the human** — it never guesses, never improvises, and never falls back
to local DB writes.

## Core model — the database is the state machine

The job `status` field is the single source of truth and the resume mechanism:

```
(scraped → local file) ──ingest──► new ──enrich──► enriched ──screen──► screened
```

- Every step reads its worklist from the DB **by status** (via MCP) and writes results back
  to the DB **by status** (via MCP), one record at a time.
- **Resumability is automatic.** If the run dies anywhere, just run this skill again: it
  re-derives its position from `status` in the DB. Already-`enriched` jobs are never
  re-enriched; already-`screened` jobs are never re-screened. Local `tmp/` files are pure
  scratch — wiping them does not lose progress.
- **Failure never advances a job.** A job that fails enrichment stays `new`; one that fails
  screening stays `enriched`. The next run retries it.

## Data boundary (every step)

- Scraping / parsing / filtering / enriching Wellfound pages is **local browser work**
  (external provider data) — local scripts + the authenticated CDP Chrome are allowed.
- **All JobLand reads and writes are JobLandMCP only.** Never write JobLand records with
  local SQL or a direct backend client. If an MCP tool/field is missing, STOP and report it.

All commands run from the profile root (scripts self-locate, so `agent/scripts/...` also
works from the monorepo checkout).

## Steps

> After **every** step: if the command exits non-zero, or output is missing/empty/unexpected,
> **STOP and surface it to the human.** Do not continue, do not improvise.

1. **Preflight + auth** — `python3 scripts/wellfound_preflight.py`, then **wellfound-check-auth**.
   Verifies Chrome on CDP 9222 (headed/Xvfb, not headless), scripts present, tmp writable,
   and a **live Wellfound session**. If there is no session or CDP is down → **STOP** (the
   user runs **wellfound-login** locally). Confirm JobLandMCP read+write tools exist.

2. **Scrape (local → file)** — **wellfound-parse-jobs**:
   `bash scripts/wellfound_scrape.sh tmp/wellfound/jobs.json`, then salary-filter
   (`python3 scripts/wellfound_salary_filter.py ...`) into `tmp/wellfound/shortlist.json`
   (+ `dropped.json`). No JobLand writes here.

3. **Fetch tracked jobs from MCP** (for dedup) —
   `python3 scripts/wellfound_fetch.py --out tmp/wellfound/tracked.json`
   (all Wellfound jobs currently in JobLand, any status).

4. **Dedup by dedup_key (scraped vs tracked)** —
   `python3 scripts/dedup_jobs.py tmp/wellfound/shortlist.json --existing tmp/wellfound/tracked.json --by dedup_key,url --out tmp/wellfound/shortlist_new.json --skipped tmp/wellfound/dedup_skipped.json`.
   Drops jobs already in JobLand and in-batch duplicates. Output = genuinely new shallow jobs.

5. **Ingest new → MCP (status=new)** —
   `python3 scripts/wellfound_ingest.py tmp/wellfound/shortlist_new.json`.
   Inserts each new job as `status=new` via MCP (duplicate URLs skipped silently). This ends
   the first-pass ingest.

6. **Fetch the enrich worklist** —
   `python3 scripts/wellfound_fetch.py --status new --out tmp/wellfound/new.json`
   (all Wellfound jobs at `status=new`, each carrying its MCP `id`).

7. **Enrich (parallel ≤5, writes DB per job)** —
   `python3 scripts/wellfound_enrich.py tmp/wellfound/new.json --concurrency 5`.
   Visits each detail page in the one authenticated Chrome, and the moment a job finishes it
   `jobs_update`s that record to `status=enriched` via MCP. Resumable from DB status.
   - **Bot-check / CAPTCHA:** the script halts immediately, brings the browser window
     on-screen at the blocking URL, and **exits 2**. Treat exit 2 as **"paused for human"**:
     STOP, ask the user to solve the slider, then re-run this skill (it resumes from DB
     status — done jobs are skipped, the blocked job is still `status=new` and retried).

8. **Fetch the screen worklist** —
   `python3 scripts/wellfound_fetch.py --status enriched --out tmp/wellfound/enriched.json`.

9. **Screen (parallel ≤5, cheap model) → screen-job skill** — run the **screen-job** skill
   over the `status=enriched` Wellfound jobs. Dispatch it on **subagents with a cheap model**
   (up to 5 in parallel), one batch slice each. Each job is judged against the CV + prefs and
   `jobs_update`d to `status=screened` with the verdict written onto the job (see
   **screen-job**). Jobs it cannot assess are left at `enriched` for the next run.

## Stop-and-wait (human-gate) — applies throughout

STOP and hand control to the human, never improvising, if any of these occur:
- no live Wellfound session, or CDP/Chrome down (step 1);
- enrich exits 2 (bot-check) — solve the slider, then re-run this skill;
- any step exits non-zero, or produces empty/garbled output;
- a JobLandMCP read/write tool or field is missing.

Never fall back to local DB writes, never fabricate data to force progress.

## Done criterion

No prose report needed. Done = the run reached a steady DB state: every intended Wellfound
job is `screened` (or deliberately left at an earlier status because it could not advance and
was surfaced to the human). Re-running this skill on a finished run is a no-op (nothing left
in `new`/`enriched`).

## When something breaks

See `references/troubleshooting.md` (login page, DataDome slider, enrich crash, 0 jobs,
MCP write failures, dedup, session transfer).
