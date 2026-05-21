---
name: scrape-and-research-job
description: Scrape any job posting URL (LLM + browser), extract structured fields, write to DB, then do full company/role research. Triggered by prompt containing "job_id=N command_id=N url=URL db=/path/jobs.db".
---

# Scrape and Research Job

## Execution Rules

- **Do NOT ask for confirmation.** Execute immediately and autonomously.
- This is a background automated task. No human is watching. Proceed through all steps.
- On any blocking error, mark command failed and exit.
- **CRITICAL: Do NOT write SQL directly to the database at any point.** The ONLY allowed DB writes are: the `status='running'` update in Step 1, `db_write_job_fields.py` in Step 3, and `db_write_research.py` in Step 5. Never run any other UPDATE or INSERT. The scripts set `jobs.status='researched'` — do not set it to anything else yourself.

## Input

Prompt contains: `job_id=<N> command_id=<N> url=<URL> db=<path>`

Parse these four values before doing anything else.

---

## Step 1: Mark command running + read job

```bash
python3 -c "
import sqlite3, json, sys
db = '<db_path>'
con = sqlite3.connect(db)
con.row_factory = sqlite3.Row
con.execute(\"UPDATE agent_commands SET status='running', started_at=datetime('now') WHERE id=?\", (<command_id>,))
con.commit()
row = con.execute('SELECT * FROM jobs WHERE id=?', (<job_id>,)).fetchone()
if not row:
    print('ERROR: job not found', file=sys.stderr)
    sys.exit(1)
print(json.dumps(dict(row)))
con.close()
"
```

---

## Step 2: Scrape the job posting URL

Navigate to `<url>` using fetch or browser tools. Read the full page content.

Extract the following fields. Use only the allowed enum values — do not invent new ones.

| Field | Type | Allowed values |
|-------|------|----------------|
| `title` | string | exact job title from posting |
| `posted_company_name` | string | company name as shown |
| `location` | string | city/region/country as stated |
| `country` | string | ISO 2-letter code; `XX` if unknown |
| `remote_scope` | enum | `remote` \| `hybrid` \| `onsite` \| `unknown` |
| `description` | string | plain text, up to 3000 chars, no HTML |
| `apply_url` | string | direct apply URL, or same as `<url>` |
| `date_posted` | string | `YYYY-MM-DD` if visible, else omit |

Write extracted fields as JSON to `/tmp/job_fields_<job_id>.json`.

---

## Step 3: Write job fields to DB

```bash
python3 /Users/zall/interviews/scripts/db_write_job_fields.py \
  --db <db_path> \
  --job-id <job_id> \
  < /tmp/job_fields_<job_id>.json
```

---

## Step 4: Research

Use web search tools to research the company and role. Sources in order:

1. Company website (infer from `posted_company_name` if not in description)
2. LinkedIn company page
3. Glassdoor
4. Crunchbase or funding source
5. News search (last 18 months): layoffs, restructuring, leadership changes, lawsuits

### A. Legitimacy Check

- Real website, active LinkedIn, real product?
- Direct employer or recruiter/agency/intermediary?
- Any mismatch between posting company and actual employer?

### B. Company Profile

- Founded year, HQ location
- LinkedIn employee count, headcount trend
- Funding: total raised, latest round type/date, lead investors, stage
- Risk news: layoffs, restructuring, leadership departures, lawsuits (last 18 months)

### C. Reputation

- Glassdoor rating, review count
- Recurring themes: management, work-life balance, layoffs, pay, engineering culture
- CEO approval rating if available

### D. Red-Flag Scan

- Job posting age / reposting evidence
- Vague or buzzword-heavy description with no concrete responsibilities
- No salary range
- Any request to pay money or buy equipment upfront
- Mismatch between company size and role scope

### E. Role Assessment (for Zall's profile: Principal/Senior IC, ~20 yrs AI/cloud/fullstack, based Spain/Germany)

- Seniority fit: Principal/Senior IC or high-impact staff role?
- Tech stack overlap: AI, cloud, full-stack, backend, architecture, platform, engineering leadership
- IC vs management
- Salary vs market for role and location (if stated)
- Remote eligibility for Spain/Germany, timezone requirements
- Visa/contract structure: employment vs contractor, country entity
- AI-native vs AI-skeptical

---

## Scoring Rubric

### Relevance Score (0–100)

- 25: seniority match for Principal/Senior IC
- 20: AI/cloud/full-stack/platform architecture overlap
- 15: remote eligibility from Spain/Germany + timezone fit
- 15: role type fit (strong IC/technical leadership preferred)
- 10: compensation signal or likely senior-market comp
- 10: product/engineering complexity + opportunity for leverage
- 5: clear hiring entity + accessible application path

### Company Trustworthiness Score (0–100)

- 20: legitimate web presence + real product
- 15: hiring entity clarity + direct employer
- 15: employee base + LinkedIn substance
- 15: funding/revenue/public-company credibility
- 10: reputation/reviews + engineering culture signal
- 10: absence of recent distress signals
- 10: job posting quality + realistic role scope
- 5: transparent compensation, location, contract terms

---

## Step 5: Write research results to DB

Produce a JSON object matching this schema **exactly**. Use only the allowed enum values listed — do not invent new ones.

```json
{
  "legitimacy_check": "Yes | Questionable | No",
  "hiring_entity_type": "direct | recruiter | agency | intermediary | unknown",
  "founded_year": 2015,
  "hq_location": "string or Not found",
  "employee_count": "string or Not found",
  "headcount_trend": "growing | flat | shrinking | unknown",
  "funding_summary": "string or Not found",
  "funding_stage": "pre-seed | seed | Series A | Series B | Series C+ | bootstrapped | public | unknown",
  "risk_news": "string or Not found",
  "glassdoor_summary": "string or Not found",
  "trustworthiness_score": 0,
  "relevance_score": 0,
  "apply_verdict": "Apply | Apply with caution | Skip",
  "one_line_summary": "string",
  "red_flag_scan": "string or None found",
  "seniority_fit": "strong_fit | good_fit | stretch | mismatch",
  "tech_stack_fit": "string",
  "ic_or_management": "IC | Management | Both | Unknown",
  "salary_assessment": "string or Not found",
  "remote_eligibility": "eligible | not_eligible | unclear",
  "visa_contract_structure": "string or Not found",
  "ai_native_assessment": "string",
  "assessment_notes": "string",
  "research_notes": "string",
  "source_urls": ["url1", "url2"]
}
```

Save JSON to `/tmp/research_<job_id>.json`, then run:

```bash
python3 /Users/zall/interviews/scripts/db_write_research.py \
  --db <db_path> \
  --job-id <job_id> \
  --command-id <command_id> \
  < /tmp/research_<job_id>.json
```

The script sets `jobs.status='researched'`, marks the scrape command `succeeded`, and sends Telegram notification. **Do not do any of this manually or with SQL.**

---

---
## Pitfalls

### Chrome Pre-Flight: Verify Local Chrome Before Any Browser Tool

**Config** (`~/.hermes/profiles/interviewprep/config.yaml`) specifies:
```yaml
browser:
  engine: auto
  cdp_url: 'http://localhost:9222'
```

**The silent fallback trap:** When Chrome is NOT running on `localhost:9222`, `browser_navigate` does NOT fail — it silently falls back to Browserbase cloud. The cloud session has no profile persistence, no saved logins, and triggers bot detection. The config `cdp_url` is ignored in this case.

**Hard rule: Before EVERY `browser_navigate` call, verify Chrome is alive:**

```bash
curl -s http://localhost:9222/json/version || echo "NOT_RUNNING"
```

If `NOT_RUNNING`, tell Zall to run `~/start-chrome.sh` first. Do not proceed with `browser_navigate` until Chrome responds.

### Browser Architecture: Local Headless Chromium, Not Cloud

The Hermes browser tool (`browser_navigate`/`browser_click`/`browser_snapshot/etc.`) routes through **agent-browser**, which launches a local **headless** Chromium on Zall's machine. There is NO Browserbase, BrowserUse, or cloud provider configured — no `BROWSERBASE_API_KEY`, no `BROWSER_USE_API_KEY`, no `NOUS_USER_TOKEN`. Never claim a cloud browser is being used.

- agent-browser defaults to **headless** mode → no visible Chrome window
- `npx agent-browser` runs locally; user agent shows `HeadlessChrome`
- The `apply-job` skill uses a **separate** Playwright script (`apply_job_filler.py`) with `headless=False` — that's the only code path producing a visible Chrome window

### If Zall Asks Why No Browser Window Appears

Explain: agent-browser runs headless locally for research tasks. The visible window only opens during application fills (Playwright headed mode). If Zall wants to see the research browser, options include:
- Run research through a Playwright script instead of agent-browser
- Configure agent-browser for headed mode (not currently set up)
- Use browser_vision for screenshots of what the headless browser is seeing

---

## Error Handling

- Missing Glassdoor, LinkedIn, Crunchbase, salary → write `Not found`, continue
- If URL is inaccessible → extract what you can from URL/domain, still complete all steps
- Hard failure:

```bash
python3 -c "
import sqlite3
con = sqlite3.connect('<db_path>')
con.execute(\"UPDATE agent_commands SET status='failed', finished_at=datetime('now'), error=? WHERE id=?\", ('<error_message>', <command_id>))
con.commit()
con.close()
"
```
