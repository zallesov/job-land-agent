---
name: job-research
description: Research a single job posting from SQLite DB. Does real web research (company, Glassdoor, funding, news). Writes structured results to company_research and job_assessments tables. Triggered by prompt containing "job_id=N command_id=N db=/path/jobs.db".
---

# Job Research

## Execution Rules

- **Do NOT ask for confirmation.** Execute immediately and autonomously.
- This is a background automated task. No human is watching. Proceed through all steps without pausing.
- On any blocking error, mark command failed and exit. Do not ask what to do.
- **CRITICAL: Do NOT write SQL directly to the database at any point.** The ONLY allowed DB writes are: the `status='running'` update in Step 1, and the `db_write_research.py` script in Step 3. Never run any other UPDATE or INSERT. The script sets `jobs.research_status='researched'` (does NOT touch `pipeline_status` or `user_status`) — do not set it to anything else yourself.
- **CRITICAL: NEVER use `research_job.py` or any Anthropic API-based research method.** This skill uses LOCAL Chrome CDP browser tools and web search. The `research_job.py` script fires an Anthropic API call and is irrelevant to the local setup. If you reach for it, stop and come back to this skill.

## Input

Prompt contains: `job_id=<N> command_id=<N> db=<path>`

Parse these three values before doing anything else.

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

## Step 1.3: Company ID check + existing research lookup

Run this immediately after Step 1, before the fit check.

```python
import sqlite3, re, sys

db = '<db_path>'
job_id = <job_id>
con = sqlite3.connect(db)
con.row_factory = sqlite3.Row

job = con.execute('SELECT * FROM jobs WHERE id=?', (job_id,)).fetchone()
company_id = job['company_id']
posted_name = (job['posted_company_name'] or '').strip()

if not company_id and posted_name:
    # Try to match an existing company by display_name or normalized_name
    normalized = re.sub(r'[^a-z0-9]', '', posted_name.lower())
    row = con.execute(
        "SELECT id FROM companies WHERE normalized_name=? OR display_name=?",
        (normalized, posted_name)
    ).fetchone()
    if row:
        company_id = row['id']
        con.execute(
            "UPDATE jobs SET company_id=?, updated_at=datetime('now') WHERE id=?",
            (company_id, job_id)
        )
        con.commit()
        print(f'Linked existing company_id={company_id} to job {job_id}')
    else:
        print(f'No company match for "{posted_name}" — create a company row manually before Step 3')

if company_id:
    research = con.execute(
        'SELECT * FROM company_research WHERE company_id=?', (company_id,)
    ).fetchone()
    if research:
        print(f'Existing research found for company_id={company_id}')
        print(dict(research))
        # Signal: SKIP Step 2
    else:
        print(f'company_id={company_id} linked but no research yet — proceed to Step 2')
else:
    print('No company_id resolved — proceed to Step 2')

con.close()
```

### If existing research found → skip Step 2

Do NOT redo web research. Instead:
- Use the existing `company_research` fields for all company data (copy `legitimacy_check`, `employee_count`, `hq_location`, `funding_summary`, `trustworthiness_score`, etc. from the DB row printed above)
- Produce the Step 3 JSON with those values, plus a fresh job-specific assessment (`relevance_score`, `apply_verdict`, `seniority_fit`, `tech_stack_fit`, `salary_assessment`, `remote_eligibility`) from the job description
- Run `db_write_research.py` normally — it detects the existing `company_research` row and skips the INSERT, only writing `job_assessments`

### If no research → proceed to Step 1.5 then Step 2

**Important:** `db_write_research.py` does NOT create company rows. It only inserts into `company_research` when `job.company_id` is already set and non-null. If `company_id` is NULL, the `company_research` INSERT is silently skipped (only `job_assessments` is written). If you want company research tracked, create the company manually before running `db_write_research.py`:

```python
import sqlite3, re
con = sqlite3.connect('jobs.db')
normalized = re.sub(r'[^a-z0-9]', '', company_name.lower())
con.execute("INSERT INTO companies (display_name, normalized_name, website_url, created_at, updated_at) VALUES (?,?,?,datetime('now'),datetime('now'))", (company_name, normalized, website_url))
company_id = con.execute("SELECT last_insert_rowid()").fetchone()[0]
con.execute("UPDATE jobs SET company_id=?, updated_at=datetime('now') WHERE id=?", (company_id, job_id))
con.commit()
con.close()
```

Then run `db_write_research.py` and it will insert into `company_research` using the linked `company_id`.

---

## Step 1.5: Quick Fit Check (before any web research)

Read the job row from Step 1 (title + description). Read `config/user.yaml` and skim `config/cv.md`.

Evaluate against these **hard no-go signals**. If ANY match → **fast exit** (go to Step 1.5 Exit, skip Step 2 entirely).

### Hard no-go signals

**Wrong seniority / pay grade:**
- Title or description contains: junior, entry-level, entry level, intern, internship, trainee, apprentice, graduate program, new grad, associate (non-senior)
- Description explicitly requires < 5 years experience
- Salary stated and clearly below senior market (< 60K EUR/year for EU roles, < 80K USD for US roles)

**Wrong role domain (non-engineering):**
- Sales, Account Executive, Account Manager, Business Development, Marketing, Growth, HR, Recruiter, Talent Acquisition, Legal, Finance, Operations (non-technical), Customer Success, Customer Support, Product Designer, UX Designer (no engineering component)

**Wrong engineering domain (not in profile):**
- Pure mobile (iOS / Android) with no backend/AI component
- Pure QA / Test Engineer with no engineering scope
- Pure DevOps / SRE with no software engineering scope
- Pure data analyst / BI analyst (no ML / AI engineering)
- Embedded / firmware / hardware engineering
- Pure frontend (no backend, no AI, no architecture)

**Clear experience mismatch:**
- Role clearly scoped for 1–4 year engineers (description tone, responsibilities, required skills all point to junior/mid)
- IC role but clearly below Staff/Senior/Principal level for a 20-year profile

### Step 1.5 Exit (fast-exit path)

If any hard no-go triggers: write the fast-exit JSON below, run `db_write_research.py`, stop.

```json
{
  "legitimacy_check": "unknown",
  "hiring_entity_type": "unknown",
  "founded_year": null,
  "hq_location": "Not found",
  "employee_count": "Not found",
  "headcount_trend": "unknown",
  "funding_summary": "Not found",
  "funding_stage": "unknown",
  "risk_news": "Not found",
  "glassdoor_summary": "Not found",
  "clutch_summary": "Not found",
  "trustworthiness_score": 50,
  "relevance_score": 5,
  "apply_verdict": "Skip",
  "one_line_summary": "Fast exit: <one-line reason why it fails the fit check>",
  "red_flag_scan": "None found",
  "seniority_fit": "mismatch",
  "tech_stack_fit": "Not evaluated — fast exit",
  "salary_range": "Not found",
  "salary_assessment": "Not evaluated — fast exit",
  "remote_eligibility": "unclear",
  "research_notes": "Skipped: profile mismatch detected from job title/description in DB.",
  "apply_url": "Not found",
  "source_urls": []
}
```

Save to `tmp/research_<job_id>.json`, then run `db_write_research.py` as in Step 3. Done — do not proceed to Step 2.

If NO hard no-go signals match → proceed to Step 2.

---

## Step 2: Research

Use web search tools to research the company and role. Research sources in order:

1. Original job posting URL
2. Company website
3. LinkedIn company page
4. Glassdoor
5. Clutch.co (`https://clutch.co/search?q=<company_name>`)
6. Crunchbase or funding source
7. News search (last 18 months): layoffs, restructuring, leadership changes, lawsuits

### A. Legitimacy Check

- Does the company have a real website, active LinkedIn, real product?
- Direct employer or recruiter/agency/intermediary?
- Any mismatch between posting company and actual employer?
- **Apply URL**: find the direct application link on the company's own careers page or ATS. Prefer a specific job page URL over a generic `/careers` page. Set `apply_url` in the result JSON — this overwrites the listing URL stored in the DB.

### B. Company Profile

- Founded year, HQ location
- LinkedIn employee count, headcount trend
- Funding: total raised, latest round type/date, lead investors, stage
- Risk news: layoffs, restructuring, leadership departures, lawsuits (last 18 months)

### C. Reputation

- Glassdoor rating, review count
- Recurring themes: management, work-life balance, layoffs, pay, engineering culture
- CEO approval rating if available
- Clutch.co: client reviews, rating, number of reviews, services focus — indicates real client base and delivery quality (especially useful for agencies/consultancies)

### D. Red-Flag Scan

- Job posting age / reposting evidence
- Vague or buzzword-heavy description with no concrete responsibilities
- No salary range
- Any request to pay money or buy equipment upfront
- Mismatch between company size and role scope

### E. Role Assessment

Read the user's profile from `config/user.yaml` (cv_path, work_style, locations, **job_preferences**, **languages**, **desired_salary**) before scoring. These free-text fields are hard constraints — apply them to the verdict:
- `job_preferences`: "no fintech" → fintech role = Skip; "startups only" → enterprise = lower score; "IC only" → management role = Skip
- `languages`: if the job requires a language not listed here → Skip or Apply with Caution
- `desired_salary`: if the posted salary is clearly below this figure, downgrade verdict to "Skip" or "Apply with Caution"
- If any field is empty, ignore it

- Seniority fit: is it a Principal/Senior IC or high-impact staff role?
- Tech stack overlap: AI, cloud, full-stack, backend, architecture, platform, engineering leadership
- IC vs management
- Salary vs market for role and location (if stated); extract as `salary_range` formatted "90-120K EUR" or "90-120K USD" — use currency matching the job's location/company; write "Not found" if absent
- Remote eligibility for user's configured locations (from config/user.yaml), timezone requirements
- Visa/contract structure: employment vs contractor, country entity
- AI-native vs AI-skeptical: does the company actually build with AI or just list it?

---

## Scoring Rubric

### Relevance Score (0–100)

- 25: seniority match for Principal/Senior IC
- 20: AI/cloud/full-stack/platform architecture overlap
- 15: remote eligibility for user's configured locations + timezone fit (read from config/user.yaml `work_style.preferred`)
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

## Step 3: Write results to DB

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
  "clutch_summary": "string or Not found",
  "trustworthiness_score": 0,
  "relevance_score": 0,
  "apply_verdict": "Strong Apply | Apply with Caution | Skip",
  "one_line_summary": "string",
  "red_flag_scan": "string or None found",
  "seniority_fit": "strong_fit | good_fit | stretch | mismatch",
  "tech_stack_fit": "string",
  "salary_range": "90-120K EUR | 90-120K USD | Not found",
  "salary_assessment": "string or Not found — compare posted salary against desired_salary from config/user.yaml; flag if clearly below or 'Not found'",
  "remote_eligibility": "eligible | not_eligible | unclear",
  "research_notes": "string",
  "apply_url": "https://... direct application URL or Not found",
  "source_urls": ["url1", "url2"]
}
```

Save JSON to `tmp/research_<job_id>.json` (project tmp folder, git-ignored), then run:

```bash
python3 scripts/db_write_research.py \
  --db <db_path> \
  --job-id <job_id> \
  --command-id <command_id> \
  < tmp/research_<job_id>.json
```

The script sets `jobs.research_status='researched'`, marks the command `succeeded`, closes any pending scrape command, and sends Telegram notification. **Do not do any of this manually or with SQL.**

### After writing: Track visited company

After research completes, add the company to `visited_companies.json` to prevent redundant research in future sessions:

```python
import json
vc = json.load(open('visited_companies.json'))
vc['company_slug'] = {'checked_at': '<today>', 'company': '<Name>', 'url': '<url>', 'verdict': '<verdict>'}
json.dump(vc, open('visited_companies.json', 'w'), indent=2)
```

Check this file before researching any company — skip companies already marked as checked.

---

## Batch Research (Multiple Jobs)

When asked to research multiple jobs (2+), use `delegate_task` to parallelize company/role research across subagents. Each subagent researches one job's company and returns structured findings. The parent agent then scores, assembles JSON, and writes all results to DB.

### Pattern

1. **Pre-step**: Query DB for job IDs to research (status='new', no pending command).
2. **Dispatch**: Spawn 2-3 parallel subagent tasks via `delegate_task(tasks=[...])`. Each task gets the job URL, company name, and title. Assign one job per task.
3. **Subagent instructions**: Each subagent navigates the job URL via browser, searches for company info (LinkedIn, funding, Glassdoor, news), and returns a structured summary. Subagents do NOT write to DB — they return raw research.
4. **Parent assembles**: Read subagent results, apply scoring rubric, produce JSON for each job, write via `db_write_research.py` loop.
5. **Second wave**: If more than 3 jobs, repeat with remaining jobs.

### Subagent context template

```
Research this job posting for company due diligence. Navigate the URL, then search for company info (LinkedIn, Glassdoor, Clutch.co, Crunchbase, news — layoffs/funding/leadership last 18 months).

Job URL: <url>
Company name: <name>
Title: <title>

Return: company legitimacy, employee count, funding, Glassdoor, risk news, red flags. Be thorough but concise.
```

---
## Pitfalls

### Chrome Pre-Flight: Verify Local Chrome Before Any Browser Tool

**Config** (`config.yaml` in an installed profile, or local `hermes-profile/config.yaml` in maintainer legacy mode) specifies:
```yaml
browser:
  engine: auto
  cdp_url: 'http://localhost:9222'
```

**The browser backend trap:** Non-CDP browser tools can use the wrong browser path. That loses profile persistence, saved logins, and visible user control.

**Hard rule: never use the non-CDP navigation tool in this agent. Before EVERY `browser_cdp` call that opens or manipulates pages, verify Chrome is alive:**

```bash
curl -s http://localhost:9222/json/version || echo "NOT_RUNNING"
```

If `NOT_RUNNING`, tell the user to run `bash start-chrome.sh` first. Do not proceed with browser operations until Chrome responds.

### Browser Architecture: Visible Local Chrome via CDP

Use `browser_cdp` against the visible Chrome instance on `http://localhost:9222`. There is NO cloud browser provider configured — no `BROWSERBASE_API_KEY`, no `BROWSER_USE_API_KEY`, no `NOUS_USER_TOKEN`. Never claim a cloud browser is being used.

- `browser_cdp(method="Target.createTarget", params={"url": "<url>"})` opens a visible Chrome tab
- `browser_cdp(method="Target.getTargets")` lists tabs and target IDs
- `browser_cdp(method="Runtime.evaluate", target_id="<target_id>", params={"expression": "document.body.textContent"})` extracts page text from the correct tab

### If the User Asks Why No Browser Window Appears

Explain: this agent should use the visible local Chrome CDP session. If no window appears, Chrome is probably not running on `localhost:9222`; run `bash start-chrome.sh`.

---

## Pitfall: Subagents timeout on batch company scraping

When dispatching subagents to check multiple company career pages, do NOT give each subagent a list of 5+ companies with curl commands. Subagents will time out at 600s on slow/unresponsive sites. Instead:

- Per-subagent scope: **1 company** with a focused task (scrape its specific ATS API)
- Prefer **direct ATS API calls** over browser navigation: Greenhouse `boards-api.greenhouse.io/v1/boards/{board}/jobs`, Ashby `jobs.ashbyhq.com/api/non-user-list?ashby_job_board_domain={board}`, Lever `api.lever.co/v0/postings/{board}`
- If board names are unknown, use browser_console on the company's careers page to extract the ATS URL first, then pass the exact API URL to the subagent
- The parent agent should do the pre-scouting (find board names) before dispatching

### JS-Heavy Pages: Extracting Full Text When Snapshot Is Truncated

Some company pages (Readymag, design-tool sites, SPAs) render content entirely in JavaScript. `browser_snapshot(full=true)` may return only a handful of interactive elements — the actual job description is invisible in the accessibility tree until the user scrolls or interacts.

**Fix:** Use `browser_console` to extract `document.body.textContent` directly:

```js
// Get full page text as one blob (preserves content order even in SPAs)
document.body.textContent.trim().substring(0, 5000)

// For targeted extraction, search for a known marker:
const t = document.body.textContent;
const idx = t.indexOf('Senior JS full-stack developer');
t.substring(idx, idx + 4000)
```

**Why `textContent` over `innerText`:** `innerText` is layout-aware and often returns empty on JS-rendered SPAs. `textContent` returns all text nodes regardless of CSS visibility. Filter out injected third-party JS blobs (Amplitude, Wellfound Apollo state) by searching for known job title markers.

**Scrolling first:** If the snapshot is truncated, `browser_scroll(direction='down')` then `browser_snapshot(full=true)` again — some SPAs lazy-load content below the fold.

### Bot-Detection Cascade: Research Source Fallbacks

When researching companies, multiple sources block non-profile browsers:

| Source | Typical result | Fallback |
|--------|---------------|----------|
| Glassdoor | Cloudflare "Humans only" challenge | Write `Not found` — no reliable workaround |
| Clutch.co | Generally accessible; search results may be JS-rendered | Use `browser_cdp`; if blocked, write `Not found` |
| Crunchbase | Cloudflare "Just a moment..." challenge | Write `Not found` |
| DuckDuckGo | "Unexpected error. Please try again." | Skip — use Bing or direct URLs |
| Bing | CAPTCHA challenge after 2-3 queries | Use Google News RSS instead |
| LinkedIn | Shows company page without login (employee count, industry, size) | Use this — it's the most reliable for headcount and industry |

**Reliable fallback for company news:** Google News RSS — not blocked by bot detection:

```bash
curl -s "https://news.google.com/rss/search?q=CompanyName&hl=en-US&gl=US&ceid=US:en" | \
  python3 -c "
import sys, xml.etree.ElementTree as ET
root = ET.fromstring(sys.stdin.read())
for item in root.findall('.//item')[:10]:
    title = item.find('title')
    pubdate = item.find('pubDate')
    if title is not None:
        print(f'{pubdate.text if pubdate is not None else \"?\"}: {title.text}')
"
```

This returns structured news items with dates — ideal for risk scanning (layoffs, restructuring, leadership changes).

**Research source priority order (revised):**
1. Original job posting URL (always works — the job is live)
2. Company website /about page (usually works)
3. LinkedIn company page (most reliable for employee count, industry, size)
4. Google News RSS (reliable for risk/news scanning)
5. Glassdoor (attempt; if blocked, mark `Not found` and continue)
6. Clutch.co `https://clutch.co/search?q=<company_name>` (attempt; if blocked, mark `Not found` and continue)
7. Crunchbase (attempt; if blocked, mark `Not found` and continue)
7. DuckDuckGo/Bing searches (use sparingly — rate-limited quickly)

### LinkedIn: Wrong Company on Generic Names

For companies with common names (ClickHouse, Maze, Pack, etc.), LinkedIn's `/company/<name>` URL may resolve to an unrelated company with the same name. The actual company page often uses a different slug like `/company/<name>inc/` or `/company/<name>hq/`.

**Fix:** If a LinkedIn company page shows an obviously wrong description (e.g. "Construction" for a database company), check:
1. The actual company website's footer for their LinkedIn URL
2. Search LinkedIn for the exact company name
3. Try `/company/<name>inc/`, `/company/<name>hq/`, `/company/<name>official/` variations
4. If still not found, write "Not found" and continue

### Silent company_research skip when company_id is null

`db_write_research.py` skips the `company_research` INSERT when `job.company_id IS NULL`. **Step 1.3 prevents this** by linking the job to an existing company (or letting `db_write_research.py` create a new one) before research runs. If you skipped Step 1.3 and company_research is missing, link the company manually then re-run `db_write_research.py`.

### Missing `clutch_summary` column in DB schema

`db_write_research.py` references a `clutch_summary` column in its `INSERT INTO company_research` statement, but the `create_db()` function in `scripts/db.py` does not create this column. If you run `db_write_research.py` on a DB initialized from scratch, you'll get:
```
sqlite3.OperationalError: table company_research has no column named clutch_summary
```

**Fix**: Add the column to the running DB:
```bash
python3 -c "
from scripts.db import get_connection
con = get_connection('jobs.db')
con.execute('ALTER TABLE company_research ADD COLUMN clutch_summary TEXT')
con.commit()
con.close()
"
```

The schema file (`scripts/db.py:create_db()`) also lacks this column — you may need to add it there for future fresh DBs, but `ALTER TABLE` on the existing DB is sufficient to unblock the current research write.


## Error Handling

- Missing Glassdoor, LinkedIn, Crunchbase, salary → write `Not found`, continue
- Hard failure → mark command failed:

```bash
python3 -c "
import sqlite3
con = sqlite3.connect('<db_path>')
con.execute(\"UPDATE agent_commands SET status='failed', finished_at=datetime('now'), error=? WHERE id=?\", ('<error_message>', <command_id>))
con.commit()
con.close()
"
```

---

## Step 4: Batch Company Prospecting (from external lists)

**Trigger:** User provides a list of company names (from Telegram posts like @zarubezhom_jobs, a message, forum, or spreadsheet column). Do NOT just report the names — proactively find domains, career pages, and matching roles.

This is a *prospecting* workflow — different from the single-job deep research in Steps 1-3 above. No DB job ID is involved until you want to add a promising role to the pipeline.

### 4.1 Domain Discovery

For each company name, find the correct domain. **Verify by visiting before reporting:**

- Try `companyname.com` first — most likely correct
- If DNS error / parked page / SSL error / wrong company → Google search
- Handle special TLDs: `.app`, `.pro`, `.org`, `.games`
- Check LinkedIn company page for the website link
- Flag as "domain not found" after exhausting reasonable options

**Common pitfalls:**
- **Domain squatters**: `insense.com` is for sale → actual company at `insense.pro`
- **Wrong TLD**: `prequel.com` is a squatter → app at `prequel.app`
- **SSL issues**: `kodland.com` has SSL errors → real site at `kodland.org`
- **Rebrands**: "Fjor Health" renamed to "Formula" — neither domain resolves
- **Cyrillic/Latin mixups**: `Сonsuno` (Cyrillic С) → `Cosuno`
- **Dead domains**: `ewa.com`, `getewa.com`, `ewa-app.com` all dead or for sale
- **Generic names**: `theopenplatform.com` is parked on GoDaddy

See `references/domain-discrepancies.md` for a complete table of verified corrections from Telegram posts.

### 4.2 Career Page Discovery

Once on the company website, find the career/jobs page:
- Common paths: `/careers`, `/jobs`, `/company`, `/about`, `/en/careers`, `/web/en/company#careers`
- Check footer and navigation for "Careers" / "Jobs" / "Join us" links
- Some sites use embedded ATS iframes (Ashby, Greenhouse, Lever) — these appear as iframes in the browser snapshot
- If JS-heavy and snapshot truncated, use `browser_console` to extract `document.body.textContent`

**No careers page ≠ no hiring.** Some companies (AIBY, Readymag, Insense, Kodland) have "We are hiring" in their footer but no public job listings. They may hire via LinkedIn or direct referrals.

### 4.3 Role Scanning

For each company with a live career page, scan open engineering roles:

**Filter for:**
- Senior/Staff/Principal level (not junior, intern, entry-level)
- Tech stack: Python, TypeScript, AI/ML, fullstack, backend, infrastructure
- Remote: EU remote, Berlin, or Spain
- Salary: €100k+ (or senior-market comp if not listed)
- AI-native companies (actually build with AI, not just list it)

**Role type priority:**
1. AI/ML Engineer, AI Engineer, ML Engineer — highest priority
2. Principal/Senior Full Stack (TypeScript/Python) — strong match
3. Staff/Principal Backend Engineer — good match
4. Platform/Security/Infrastructure Engineer — possible

### 4.4 Reporting

Present findings as a table: Company name | Role title | Salary | Remote | Verdict. Call out the best matches (top 2-3), companies with career pages but no visible SWE roles, and companies where domain wasn't found.

### 4.5 Pipeline Integration

If the user asks to add a role to the database:
1. Open the job posting URL in the browser
2. Run `python3 scripts/add_job_by_url.py --url <url>`
3. Report the screening result

### Pitfalls for Batch Prospecting

- **Trust no domain from a Telegram post** — Posts frequently use the company's brand name as the supposed domain, not its actual domain. Always verify by visiting.
- **Bot detection on research sources** — Glassdoor, Crunchbase, and DuckDuckGo all block non-profile browsers. Use Google News RSS for risk scanning. LinkedIn company pages are the most reliable for headcount/industry.
- **Subagent scope for large lists** — When dispatching subagents for 15+ companies, limit each subagent to 1 company. Do NOT batch 5+ companies per subagent — they'll time out on slow/unresponsive sites.
- **Prefer direct ATS API calls** — Greenhouse `boards-api.greenhouse.io/v1/boards/{board}/jobs`, Ashby `jobs.ashbyhq.com/api/non-user-list?ashby_job_board_domain={board}`, Lever `api.lever.co/v0/postings/{board}`
