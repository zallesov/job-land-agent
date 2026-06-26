---
name: wellfound-smoke-test
description: Use to validate the Wellfound pipeline end-to-end on a tiny sample (scrape, salary-filter, dedup, enrich 1-3 jobs) with no JobLand writes, before running a full batch.
---

# Wellfound Smoke Test

Fast confidence check of auth, selectors, and enrichment before a full run. **No JobLand
writes** by default.

## Steps

```bash
# 0. preflight
python3 scripts/wellfound_preflight.py

# 1. scrape the feed (full scroll is fine; we only use a few)
bash scripts/wellfound_scrape.sh

# 2. salary filter
python3 scripts/wellfound_salary_filter.py

# 3. dedup (needs tracked.json from JobLand via MCP; if absent, skip — treats all as new)
python3 scripts/dedup_jobs.py --by url || cp tmp/wellfound/shortlist.json tmp/wellfound/shortlist_new.json

# 4. enrich just 1-3 jobs into a throwaway file
python3 scripts/wellfound_enrich.py --out tmp/wellfound/smoke.json \
    --checkpoint tmp/wellfound/smoke.jsonl --no-resume --limit 3
```

## Pass criteria

Inspect `tmp/wellfound/smoke.json`:
- `enriched_ok` equals the limit (e.g. 3/3)
- each job has a real `company` (not `?`), non-empty `description`, and an `apply_url`
- NOT all identical `descLen` (identical lengths = DataDome block pages, not real data)

If jobs come back blocked (DataDome) or `enriched_ok` is 0 → see **wellfound-troubleshooting**
(`wellfound-flow/references/troubleshooting.md`). Do not proceed to a full batch until the
smoke test returns real data.

## Optional one controlled write

To also validate the MCP write path, take ONE job from `smoke.json` and `jobs_create` it
via JobLandMCP using the **jobland-field-mapping** reference, then confirm with
`jobs_find_by_url`. Delete it afterward if it was only a test.
