---
name: wellfound-enrich-jobs
description: Use to enrich the Wellfound status=new jobs by visiting each detail page (up to 5 concurrent) and writing each result back into JobLand via JobLandMCP (status -> enriched), one job at a time.
---

# Wellfound Enrich Jobs

Adds the fields the feed cannot give (company, external apply URL, full description, real
compensation/location), and **writes each finished job straight back into JobLand**
(`status` → `enriched`) the moment it is done. Browser work is local; **JobLand writes are
JobLandMCP only** (via `scripts/mcp_client.py`, the sanctioned Python MCP path).

## Preconditions

- The enrich worklist file exists: `tmp/wellfound/new.json` — the Wellfound jobs at
  `status=new`, each carrying its MCP `id` (produced by
  `python3 scripts/wellfound_fetch.py --status new --out tmp/wellfound/new.json`).
- Live session + visible CDP Chrome on 9222.

## Run (local, parallel, DB-writing, resumable)

```bash
python3 scripts/wellfound_enrich.py tmp/wellfound/new.json --concurrency 5
```

- Drives **up to 5 concurrent tabs** in the one authenticated Chrome via Playwright
  `connect_over_cdp` (reuses `contexts[0]` cookies — shared login). agent-browser's
  isolated `--session` is NOT used here: it would lose the auth.
- Per job it merges SSR `__NEXT_DATA__` (title, description, compensation, locations,
  remote, jobType, source) with the rendered DOM (`apply_url` from the "Apply" anchor;
  `null` apply_url = in-app platform apply, handled later by `apply-job`).
- **Writes to JobLand per job.** The moment a job finishes enriching, the script
  `jobs_update`s that record via MCP with the enriched fields and `status=enriched`
  (mapping in `references/jobland-field-mapping.md`; note the PB field is `salary_range`).
  Progress is durable per job — there is **no separate "agent writes it later" step**.
- **Resumable from DB status.** Because each job is advanced to `enriched` in the DB as it
  finishes, re-running after a crash simply re-fetches `status=new` and only the unfinished
  jobs come back. A local JSONL checkpoint (`<out>.jsonl`) is kept as secondary scratch, but
  the DB is the source of truth — wiping `tmp/` does not lose progress.

Flags: `--limit N` (smoke a few first), `--no-db` (dry run, file output only, no JobLand
writes), `--concurrency` (default 5). A `--headless` mode exists for non-DataDome providers;
Wellfound's DataDome blocks headless, so use the default CDP-connect mode (on a server: a
headed Chrome under Xvfb).

## Bot-check during enrichment

If a DataDome slider / "verify you are human" interstitial appears mid-batch, the script
**halts immediately**, does **not** advance the blocked job (it stays `status=new`), brings
the browser window **on-screen** at the blocking URL, and exits code **2**.

What to do:
1. Solve the slider by hand in the window that popped up (CDP-connect mode).
2. Re-run the same command. It **resumes from DB status**: already-`enriched` jobs are not in
   the `status=new` worklist anymore; the blocked job and the rest are retried with a fresh
   DataDome clearance cookie.

Treat exit code 2 as **"paused for human"**, not a failure.

## What NOT to overwrite

On a job already past `enriched` (e.g. `screened`) or carrying user fields, only enrich-owned
fields are written; never touch `user_status` or screening fields. See
`references/jobland-field-mapping.md` ("What NOT to overwrite on update").

## Done criterion

Done = every job from the `status=new` worklist is now `status=enriched` in JobLand (or was
left at `new` because it was bot-blocked / errored, to be retried next run). No prose report
needed; the DB state is the result.
