# Manual Telegram Job → SQLite Workflow

When a user pastes a job from a Telegram channel (e.g. @dev_connectablejobs), the agent must extract structured info and insert into SQLite. This is a common ad-hoc flow (not scraper-driven).

## Steps

### 1. Parse the Telegram message

Extract these fields from the user's message:

| Field | Example |
|-------|---------|
| `company_name` | Akvelon |
| `title` | Senior / Lead Java SDE (GL) |
| `location` | Krakow, Poland |
| `remote_scope` | office (if in-office), remote, hybrid |
| `url` | PeopleForce/Lever/Greenhouse link from the post |
| `source` | dev_connectablejobs (Telegram channel) |
| `hr_contact` | @AKVELON_HR (if provided) |
| `referral_code` | @dev_connectablejobs (if provided — user should mention this when applying) |

### 2. Check existing records

```sql
-- Check if company exists (companies.normalized_name is the dedup key)
SELECT id, display_name FROM companies WHERE normalized_name = 'akvelon';

-- Check if job already exists (jobs.url is UNIQUE)
SELECT id, status FROM jobs WHERE url = '<url>';
```

### 3. Insert company (if new)

```sql
INSERT INTO companies (display_name, normalized_name, website_url, domain, linkedin_url)
VALUES ('Akvelon', 'akvelon', 'https://akvelon.com', 'akvelon.com', 'https://linkedin.com/company/akvelon');
```

### 4. Insert job

```sql
INSERT INTO jobs (url, provider, company_id, title, description, apply_url, location, country, remote_scope, status, source_payload_json)
VALUES ('<url>', '<source_channel>', <company_id>, '<title>', '<description if available>', NULL, '<city>, <country>', '<country>', '<remote_scope>', 'new',
  '{"source": "telegram", "channel": "dev_connectablejobs", "hr_contact": "@AKVELON_HR", "referral_code": "@dev_connectablejobs"}');
```

Note: `source_payload_json` stores metadata that doesn't fit in top-level columns — HR contacts, referral codes, channel info, etc.

### 5. Insert company research

```sql
INSERT INTO company_research (company_id, researched_at, research_status, company_overview, founders_ceos, employees_count, year_founded, headquarters, clients, trustworthiness_score, glassdoor_summary, linkedin_summary, research_notes, research_data_json)
VALUES (<company_id>, datetime('now'), 'completed',
  '<2-3 sentence overview>',
  '<founder names + background>',
  <employee_count>,
  <year_founded>,
  '<HQ location>',
  '<notable clients>',
  <1-100 score>,
  '<Glassdoor details>',
  '<LinkedIn details>',
  '<freeform research notes>',
  '{"sources": ["company_website", "glassdoor", "linkedin"]}');
```

### 6. Insert job assessment

```sql
INSERT INTO job_assessments (job_id, assessed_at, assessment_status, relevance_score, apply_verdict, skill_match_notes, gap_notes, interview_difficulty, notes, assessment_data_json)
VALUES (<job_id>, datetime('now'), 'completed',
  <1-100 score>,
  '<yes | maybe | no>',
  '<matched skills: Kafka, GCP, Java, ...>',
  '<gap skills: Go, ...>',
  '<expected difficulty estimate>',
  '<freeform assessment notes>',
  '{"scoring_rationale": "<why this score>"}');
```

### 7. Final status

```sql
-- Status is 'new'. ONLY advance to 'researched' when the user explicitly asks for research.
-- Do NOT auto-transition. The scrape/ingest phase always ends with status='new'.
UPDATE jobs SET updated_at=datetime('now') WHERE id=<job_id>;
```

### 8. Report to user

Return a structured summary to the user:

> ✅ **Akvelon** (ID 30) → **Senior / Lead Java SDE (GL)** (ID 60)
> 📍 Krakow, Poland | 🏢 Office | 🤝 @AKVELON_HR (mention @dev_connectablejobs)
> 
> **Assessment:** Relevance 65/100 → Verdict: maybe
> **Trust:** 85/100 (26yr company, 1000+ employees, Microsoft/Google clients)
> **Match:** Kafka, GCP, distributed systems ✓
> **Gap:** Go (not on CV), Krakow office-first (relocation required)
> 
> DB inserted: companies.id=30, jobs.id=60, status='new'

## Pitfalls

- **Don't skip the DB write**: The report to user comes AFTER the DB insert, not before. If you write the report first, you'll likely forget to insert.
- **normalized_name** is the dedup key for companies — always lowercase, no spaces, strip periods/LLC/etc.
- **jobs.url** is UNIQUE — use INSERT OR IGNORE if there's any chance of duplicates
- **HR contact** belongs in `source_payload_json`, not in the company or job top-level columns
- **Apply URL** may be the same as the job URL if no separate application link exists — that's fine, set to NULL or the same URL
- **Status is always 'new' after Phase 1**: Do NOT set status to 'assessed' or 'researched' — those are not Phase 1 statuses. The assessment is a separate, explicit Phase 2 step.
- **Do not merge steps 5-6-7 into phase 1**: Company research and job assessment are NOT part of the initial scrape/ingest. They are Phase 2 work triggered only when the user says "research this job".
