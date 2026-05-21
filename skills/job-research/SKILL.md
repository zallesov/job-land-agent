---
name: job-research
description: Research a single job posting from SQLite DB. Does real web research (company, Glassdoor, funding, news). Writes structured results to company_research and job_assessments tables. Triggered by prompt containing "job_id=N command_id=N db=/path/jobs.db".
---

# Job Research

## Execution Rules

- **Do NOT ask for confirmation.** Execute immediately and autonomously.
- This is a background automated task. No human is watching. Proceed through all steps without pausing.
- On any blocking error, mark command failed and exit. Do not ask what to do.
- **CRITICAL: Do NOT write SQL directly to the database at any point.** The ONLY allowed DB writes are: the `status='running'` update in Step 1, and the `db_write_research.py` script in Step 3. Never run any other UPDATE or INSERT. The script sets `jobs.status='researched'` — do not set it to anything else yourself.
- **CRITICAL: NEVER use `research_job.py` or any Anthropic API-based research method.** This skill uses LOCAL browser tools (agent-browser headless Chromium) and web search. The `research_job.py` script fires an Anthropic API call and is irrelevant to the local setup. If you reach for it, stop and come back to this skill.

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
  "trustworthiness_score": 50,
  "relevance_score": 5,
  "apply_verdict": "Skip",
  "one_line_summary": "Fast exit: <one-line reason why it fails the fit check>",
  "red_flag_scan": "None found",
  "seniority_fit": "mismatch",
  "tech_stack_fit": "Not evaluated — fast exit",
  "ic_or_management": "Unknown",
  "salary_range": "Not found",
  "salary_assessment": "Not evaluated — fast exit",
  "remote_eligibility": "unclear",
  "visa_contract_structure": "Not found",
  "ai_native_assessment": "Not evaluated — fast exit",
  "assessment_notes": "Fast exit — no web research performed. Reason: <specific trigger that matched>",
  "research_notes": "Skipped: profile mismatch detected from job title/description in DB.",
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
5. Crunchbase or funding source
6. News search (last 18 months): layoffs, restructuring, leadership changes, lawsuits

### A. Legitimacy Check

- Does the company have a real website, active LinkedIn, real product?
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

### E. Role Assessment

Read the user's profile from `config/user.yaml` (cv_path, work_style, locations) before scoring. The scoring dimensions below apply generically.

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
  "trustworthiness_score": 0,
  "relevance_score": 0,
  "apply_verdict": "Apply | Apply with caution | Skip",
  "one_line_summary": "string",
  "red_flag_scan": "string or None found",
  "seniority_fit": "strong_fit | good_fit | stretch | mismatch",
  "tech_stack_fit": "string",
  "ic_or_management": "IC | Management | Both | Unknown",
  "salary_range": "90-120K EUR | 90-120K USD | Not found",
  "salary_assessment": "string or Not found",
  "remote_eligibility": "eligible | not_eligible | unclear",
  "visa_contract_structure": "string or Not found",
  "ai_native_assessment": "string",
  "assessment_notes": "string",
  "research_notes": "string",
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

The script sets `jobs.status='researched'`, marks the command `succeeded`, closes any pending scrape command, and sends Telegram notification. **Do not do any of this manually or with SQL.**

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
Research this job posting for company due diligence. Navigate the URL, then search for company info (LinkedIn, Glassdoor, Crunchbase, news — layoffs/funding/leadership last 18 months).

Job URL: <url>
Company name: <name>
Title: <title>

Return: company legitimacy, employee count, funding, Glassdoor, risk news, red flags. Be thorough but concise.
```

---
## Pitfalls

### Chrome Pre-Flight: Verify Local Chrome Before Any Browser Tool

**Config** (`hermes-profile/config.yaml`) specifies:
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

If `NOT_RUNNING`, tell the user to run `~/start-chrome.sh` first. Do not proceed with `browser_navigate` until Chrome responds.

### Browser Architecture: Local Headless Chromium, Not Cloud

The Hermes browser tool (`browser_navigate`/`browser_click`/`browser_snapshot/etc.`) routes through **agent-browser**, which launches a local **headless** Chromium on the user's machine. There is NO Browserbase, BrowserUse, or cloud provider configured — no `BROWSERBASE_API_KEY`, no `BROWSER_USE_API_KEY`, no `NOUS_USER_TOKEN`. Never claim a cloud browser is being used.

- agent-browser defaults to **headless** mode → no visible Chrome window
- `npx agent-browser` runs locally; user agent shows `HeadlessChrome`
- The `apply-job` skill uses a **separate** Playwright script (`apply_job_filler.py`) with `headless=False` — that's the only code path producing a visible Chrome window

### If the User Asks Why No Browser Window Appears

Explain: agent-browser runs headless locally for research tasks. The visible window only opens during application fills (Playwright headed mode). If the user wants to see the research browser, options include:
- Run research through a Playwright script instead of agent-browser
- Configure agent-browser for headed mode (not currently set up)
- Use browser_vision for screenshots of what the headless browser is seeing

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

When researching companies, multiple sources block headless browser IPs:

| Source | Typical result | Fallback |
|--------|---------------|----------|
| Glassdoor | Cloudflare "Humans only" challenge | Write `Not found` — no reliable workaround |
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
6. Crunchbase (attempt; if blocked, mark `Not found` and continue)
7. DuckDuckGo/Bing searches (use sparingly — rate-limited quickly)

### Silent company_research skip when company_id is null

When a job row has `company_id IS NULL` (common for newly scraped jobs that haven't been matched to a company record), `db_write_research.py` skips the `company_research` INSERT entirely (line 46: `if company_id:`). The research data still lands in `job_assessments.raw_assessment_json`, but there is no dedicated company_research row. This is by design — company_research is keyed by company_id, not job_id. If you need the company research persisted standalone, set `company_id` on the job row first.

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
