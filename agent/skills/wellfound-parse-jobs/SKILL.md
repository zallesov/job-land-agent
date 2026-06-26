---
name: wellfound-parse-jobs
description: Use to scrape the Wellfound saved-search feed (/jobs) — scroll to load all cards, parse to JSON, and salary-filter into a shortlist for enrichment. Local browser work only.
---

# Wellfound Parse Jobs

Scrapes the account's saved-search feed and produces a salary-filtered shortlist. Pure
local browser work — no JobLand writes happen here.

## Preconditions

- Live session (run **wellfound-check-auth** first).
- Visible CDP Chrome on 9222 (see `read-web-pages` for runtime + the `--cdp 9222` rule).

## Steps

1. **Scrape the feed** (saved search is applied server-side — nothing to type):
   ```bash
   bash scripts/wellfound_scrape.sh tmp/wellfound/jobs.json
   ```
   It opens `/jobs`, exhausts the **infinite scroll** (scroll `document.scrollingElement`
   to bottom, wait, repeat until the row count is stable for 3 passes), then writes every
   card: `id, url, title, location, compensation, salary, equity, posted,
   recruiterActive, reposted`.

2. **Salary filter** (floor from `config/user.yaml` `desired_salary`):
   ```bash
   python3 scripts/wellfound_salary_filter.py tmp/wellfound/jobs.json \
       --out-dir tmp/wellfound
   ```
   - `shortlist.json` ← **pass** (max comp ≥ floor) + **unknown** (no salary shown) → enrich
   - `dropped.json`   ← **drop_low** (max comp < floor) → audit trail

3. Report counts (total / shortlist=pass+unknown / dropped) and hand `shortlist.json` to
   **dedup-jobs** (pre-enrich, `--by url`; removes already-tracked jobs before enrichment).

## What the feed does and does NOT give

- Feed is **client-fetched** — its `__NEXT_DATA__` has zero job refs. Parse the rendered
  DOM, not the SSR payload.
- **No company name** in the feed (cards are role-level). Company comes during enrichment
  from the detail page.
- Use **prefix class selectors** (wellfound ships build-hashed CSS): rows are
  `[class*="styles_jobListingList__"] [class*="styles_component__Ey28k"]`; fields are
  `[class*="styles_title__"]`, `[class*="styles_location__"]`,
  `[class*="styles_compensation__"]`. Hash suffixes change across deploys; prefixes are stable.

### If it returns 0 (or far too few) jobs

1. Confirm logged in (avatar on `/jobs`) — a login/`restricted` page yields 0. See
   **wellfound-troubleshooting**.
2. Check the row selector still matches:
   `agent-browser --cdp 9222 eval 'document.querySelectorAll(`[class*="styles_jobListingList__"] [class*="styles_component__Ey28k"]`).length'`
   If 0, inspect a card (`a[href*="/jobs/"]` → climb parents) and update the prefixes in
   `scripts/wellfound_scrape.sh`.
3. A few jobs but a large result count shown = scroll plateaued → scroll harder / wait
   longer. Do **not** switch to GraphQL (not part of this approach).

## Salary filter notes

Coarse on purpose: reads only the card's salary string, does NOT convert currencies
(€/$/£ k-numbers compared directly to the floor), ignores equity `%`, and **keeps**
salary-unknown roles for enrichment. Known gap: Indian `₹NNL` (Lakh) is not understood.
It shrinks the enrichment batch — it is not the final apply/skip decision.

Output dir `tmp/wellfound/` (under the profile root) is gitignored in the repo.
