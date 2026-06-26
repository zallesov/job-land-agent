---
name: dedup-jobs
description: Provider-agnostic job dedup. Drops jobs already tracked in JobLand (and in-batch duplicates) by company+title, apply_url, and url. One dedup for every provider — catches the same role re-posted across sites.
---

# Dedup Jobs

One shared dedup for all providers. Removes jobs already in JobLand and duplicates within
the batch, matching on any of three keys:

- `dedup_key = "{company}::{title}"` — cross-provider: the same role re-posted on another
  site shares company+title even with a different URL.
- `apply_url` (normalized) — cross-provider: same ATS application link.
- `url` (normalized) — same-provider: the exact posting.

A job is a duplicate if **any** available key is already tracked or already seen earlier
in the batch. Jobs only carry the keys they have at the current stage, so this skill runs
at two points in a provider flow:

- **Before enrichment** — feed jobs usually have only `url` → same-provider dedup
  (cheap; avoids enriching jobs already tracked). Use `--by url`.
- **After enrichment, before writing to JobLand** — jobs now have company+title+apply_url
  → cross-provider dedup. Use the default `--by dedup_key,apply_url,url`.

## Step 1 — Fetch tracked keys from JobLand (JobLandMCP only)

Pull existing job keys into a tracked file. Prefer a **batch** read (`jobs_list` /
`jobs_search`) over one call per job. Write either form:

```json
{ "dedup_keys": ["Acme::Senior Engineer", ...],
  "urls":       ["https://...", ...],
  "apply_urls": ["https://...", ...] }
```

or just the list of existing job objects (the script reads their
`company/title/url/apply_url`). Do not read JobLand with local scripts/SQL — MCP only.

## Step 2 — Local set-difference

```bash
# pre-enrich (same-provider, url only)
python3 scripts/dedup_jobs.py tmp/<provider>/shortlist.json \
    --existing tmp/<provider>/tracked.json --by url \
    --out tmp/<provider>/shortlist_new.json --skipped tmp/<provider>/dedup_skipped.json

# post-enrich (cross-provider: company+title, apply_url, url)
python3 scripts/dedup_jobs.py tmp/<provider>/enriched.json \
    --existing tmp/<provider>/tracked.json \
    --out tmp/<provider>/enriched_new.json --skipped tmp/<provider>/enriched_dupes.json
```

Matching: `url`/`apply_url` are normalized (scheme/query/trailing-slash stripped;
Wellfound `/jobs/<id>` reduced to its id); `dedup_key` is compared casefolded, so it lines
up with the DB's `"{company}::{title}"` values. Skipped jobs get a `dedup_reason` field.

## Report

Report input count, tracked-keys count, new vs duplicate, and (post-enrich) the
`dedup_reason` breakdown (how many matched by company+title vs apply_url vs url).
