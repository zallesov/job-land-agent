# Ad-Hoc URL Addition Workflow

When the user pastes a raw job posting URL (not from Telegram, not from a scraper) and says "add this job + research it", follow this sequence.

## Phase 1: Scrape + Insert (status = 'new')

### 1. Navigate to URL and extract content

```
browser_navigate(url)
browser_scroll(direction='down')
browser_snapshot(full=true)  # May be truncated on JS-heavy pages
```

If snapshot is truncated (few elements, missing description):
```
browser_console(expression="document.body.textContent.trim().substring(0, 5000)")
```

Block of JS/Apollo/Amplitude garbage may precede the actual content. Search for the job title marker to find the right offset. Repeat with `.substring(5000, 10000)` if more content needed.

### 2. Extract structured fields

| Field | Source |
|-------|--------|
| `title` | Exact title from the posting |
| `posted_company_name` | Company name as shown |
| `location` | City/region/country as stated |
| `remote_scope` | `remote`, `hybrid`, `onsite`, `unknown` |
| `description` | Full plain-text, no HTML, max 3000 characters |
| `apply_url` | Same as URL, or separate apply link if found |
| `date_posted` | `YYYY-MM-DD` if visible |

### 3. Insert company (if new)

```sql
-- Check first
SELECT id, display_name FROM companies WHERE normalized_name = '<lowercase-name>';

-- Insert if new
INSERT INTO companies (display_name, normalized_name, website_url, domain)
VALUES ('Readymag', 'readymag', 'https://readymag.com', 'readymag.com');
```

`normalized_name` = lowercase, no spaces, strip periods/LLC/etc. It's the dedup key.

### 4. Insert job

```sql
INSERT INTO jobs (url, provider, company_id, title, description, apply_url, location, country, remote_scope, status, source_payload_json)
VALUES (
  '<url>',
  'manual',
  <company_id>,
  '<title>',
  '<description>',
  '<apply_url>',
  '<location>',
  'XX',  -- ISO country code, XX if unknown
  '<remote_scope>',
  'new',
  '{}'
);
```

`jobs.url` is UNIQUE — use `INSERT OR IGNORE` if duplicates possible.
Status is ALWAYS `'new'` at this point. Never `'researched'` or `'assessed'`.

### 5. Create agent_command for research

```sql
INSERT INTO agent_commands (command_type, status, payload_json, created_at)
VALUES ('research_job', 'pending', '{"job_id": <job_id>, "url": "<url>"}', datetime('now'));
```

Note the returned `command_id` — you'll need it for the research phase.

### 6. Report to user

Minimal summary: company name, job ID, title, location, remote status. Then offer to research.

## Phase 2: Research (status = 'researched')

Follow the `job-research` skill with `job_id=<N> command_id=<M> db=/Users/zall/interviews/jobs.db`.

Key steps:
1. Mark command running
2. Research (company site, LinkedIn, Google News RSS, Glassdoor/Crunchbase)
3. Write results via `db_write_research.py`

## Pitfalls

- **Don't set status='researched' in Phase 1** — only the `db_write_research.py` script sets that
- **Browser may have stale session** — if `browser_navigate` shows Wellfound/Apollo content instead of the target page, the browser has a cached session. Re-navigate to the exact URL.
- **TextContent has injected JS** — Amplitude, Wellfound Apollo state, Cloudflare challenge scripts get mixed into `document.body.textContent`. Always search for the job title as an anchor before extracting.
- **command_id ≠ job_id** — the `agent_commands.id` is a separate auto-increment from `jobs.id`. Track both.
- **`source_payload_json`** — use `'{}'` for manual additions (no Telegram metadata, no HR contacts). For Telegram additions, see `manual-telegram-to-sqlite-workflow.md`.
