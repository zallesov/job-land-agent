# JobLandAgent Sub-projects C+B: SOUL, Skills & README Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rewrite `hermes-profile/SOUL.md` as JobLandAgent, generalize existing skills to remove personal data, create four new skills (onboarding, check-auth, run-scraping-pipeline, add-job-by-url), and write `README.md`.

**Architecture:** All changes are markdown/YAML text files. No Python code changes. Execute in order: SOUL.md → generalize existing skills → new skills → README → dashboard title.

**Tech Stack:** Markdown, YAML, Bash snippets in skill files

**Prerequisite:** Sub-project A must be complete (config/user.yaml.example exists, skills archive done).

---

## Chunk 1: SOUL.md Rewrite + Existing Skill Generalization

### Task 1: Rewrite hermes-profile/SOUL.md as JobLandAgent

**Files:**
- Modify: `hermes-profile/SOUL.md`

**Context:** Current SOUL.md is "InterviewPrep" persona with hardcoded "Zall" references and no knowledge of the job pipeline. The browser rules section (lines 3–12) must be preserved verbatim. Only the identity paragraph and knowledge sections change.

- [ ] **Step 1: Write the new SOUL.md**

Use the Write tool to replace the entire content of `hermes-profile/SOUL.md`. Write the text between the `~~~` fences below — the `~~~` lines are plan markers, NOT part of the file:

~~~
You are JobLandAgent, an autonomous job search assistant.
You help users find, evaluate, and apply to software engineering jobs
by scraping job boards, enriching listings with AI, scoring them
against the user's CV, and managing the application pipeline.

## Browser Rules (follow exactly, no exceptions)

Chrome runs persistently at `http://localhost:9222` with a saved session profile.

- **Always use native browser tools**: `browser_navigate`, `browser_click`, `browser_snapshot`, `browser_type`, etc.
- **Never launch a new browser.** Never pass headless flags. Never use `--user-data-dir`. Chrome is already running.
- **Never use Playwright MCP tools** (`mcp__playwright__*`) for job research or scraping — they connect to the same Chrome but tool consistency matters; prefer native browser tools.
- If `browser_navigate` fails with "no browser", tell the user to run `~/start-chrome.sh` first, then retry.
- Sessions (Greenhouse login, JobLeads login, etc.) persist in the profile — do not re-authenticate unless explicitly told the session expired.

## Always-Known Facts

- **User config:** `config/user.yaml` — cv_path, locations, providers, search_terms, user identity, work_style
- **Chrome:** must be running at `localhost:9222` before any scraping or auth. Start with `~/start-chrome.sh`.
- **Dashboard:** `http://localhost:3000` (start with `cd dashboard && npm run dev`)
- **DB path:** from `config/user.yaml` `db_path` field (default: `jobs.db`)
- **Skills dir:** `skills.external_dirs` in `hermes-profile/config.yaml` must be `["../skills"]`

### Job Status Lifecycle

```
listed → new → interesting → researching → researched → draft_ready
                                                       → not_interested
                                                       → applied → interviewing → rejected
                           → enrich_failed
                           → sanity_failed
                           → archived
```

## Skill Reference

| Skill | Invoke when |
|---|---|
| `onboarding` | User is setting up for the first time |
| `check-auth` | Before scraping; when a provider login expires |
| `run-scraping-pipeline` | User asks to scrape (all providers or a specific one/location) |
| `job-research` | User asks to research or score a specific job |
| `add-job-by-url` | User provides a job posting URL |
| `apply-job` | User says "apply to job N" |
| `enrich-job` | User asks to enrich a specific job |
| `sanity-check-job` | User asks to sanity-check a specific job |
~~~

- [ ] **Step 2: Verify SOUL.md has no personal names**

```bash
grep -i "zall\|aleksandr\|zallesov\|interviewprep" hermes-profile/SOUL.md
# Expected: no output (no personal references)
```

- [ ] **Step 3: Commit**

```bash
git add hermes-profile/SOUL.md
git commit -m "feat: rewrite SOUL.md as JobLandAgent identity"
```

---

### Task 2: Generalize skills/job-research/SKILL.md

**Files:**
- Modify: `skills/job-research/SKILL.md`

**Context:** The skill has hardcoded "Zall" in the role assessment section (line 83: "Zall's profile: Principal/Senior IC, ~20 yrs AI/cloud/fullstack, based Spain/Germany"), hardcoded DB path (`/Users/zall/interviews/tmp/research_<job_id>.json` and `/Users/zall/interviews/scripts/db_write_research.py`), and hardcoded `~/.hermes/profiles/interviewprep/config.yaml` in the pitfalls section.

- [ ] **Step 1: Read the full skill file**

Read `skills/job-research/SKILL.md` in full before editing.

- [ ] **Step 2: Replace Zall role assessment with generic version**

Find (around line 83):
```markdown
### E. Role Assessment (for Zall's profile: Principal/Senior IC, ~20 yrs AI/cloud/fullstack, based Spain/Germany)
```

Replace with:
```markdown
### E. Role Assessment

Read the user's profile from `config/user.yaml` (cv_path, work_style, locations) before scoring. The scoring dimensions below apply generically.
```

- [ ] **Step 3: Replace hardcoded tmp path with generic**

Find all occurrences of `/Users/zall/interviews/tmp/research_<job_id>.json` and replace with `tmp/research_<job_id>.json`.

Find `/Users/zall/interviews/scripts/db_write_research.py` and replace with `scripts/db_write_research.py`.

- [ ] **Step 4: Replace hardcoded hermes profile path**

Find:
```
~/.hermes/profiles/interviewprep/config.yaml
```
Replace with:
```
hermes-profile/config.yaml
```

- [ ] **Step 5: Replace scoring rubric personal references**

Find the remote eligibility scoring line in the Relevance Score rubric:
```markdown
- 15: remote eligibility from Spain/Germany + timezone fit
```
Replace with:
```markdown
- 15: remote eligibility for user's configured locations + timezone fit (read from config/user.yaml `work_style.preferred`)
```

Find in Role Assessment body (around line 89):
```markdown
- Remote eligibility for Spain/Germany, timezone requirements
```
Replace with:
```markdown
- Remote eligibility for user's configured locations (from config/user.yaml), timezone requirements
```

- [ ] **Step 6: Remove personal references in Pitfalls section**

Find (around line 213 — Chrome Pre-Flight pitfall):
```markdown
tell Zall to run `~/start-chrome.sh` first
```
Replace with:
```markdown
tell the user to run `~/start-chrome.sh` first
```

Find (around line 217 — Browser Architecture section):
```markdown
launches a local **headless** Chromium on Zall's machine
```
Replace with:
```markdown
launches a local **headless** Chromium on the user's machine
```

Find the section heading (around line 223):
```markdown
### If Zall Asks Why No Browser Window Appears
```
Replace with:
```markdown
### If the User Asks Why No Browser Window Appears
```

Find in the body of that section (around line 225):
```markdown
If Zall wants to see the research browser
```
Replace with:
```markdown
If the user wants to see the research browser
```

- [ ] **Step 7: Remove hardcoded IP address**

Find (around line 263 — Bot-Detection section):
```markdown
block headless browser IPs (213.194.151.53 based in Spain)
```
Replace with:
```markdown
block headless browser IPs
```

- [ ] **Step 8: Verify no personal names or absolute paths remain**

```bash
grep -n "Zall\|zall\|/Users/\|213\.194\|Spain/Germany\|interviewprep" skills/job-research/SKILL.md
# Expected: no output
```

- [ ] **Step 9: Commit**

```bash
git add skills/job-research/SKILL.md
git commit -m "feat: generalize job-research skill — remove personal references, use config/user.yaml"
```

---

### Task 3: Generalize skills/apply-job/SKILL.md

**Files:**
- Modify: `skills/apply-job/SKILL.md`

**Context:** The skill has hardcoded name/email/LinkedIn/CV/resume path (Step 4 fixed fields JSON, around line 74–94) and hardcoded `cat /Users/zall/interviews/cv_master_content.md` (Step 2). Must read these from `config/user.yaml` at runtime.

- [ ] **Step 1: Read the full skill file**

Read `skills/apply-job/SKILL.md` in full before editing.

- [ ] **Step 2: Replace Step 2 (Read CV content) with user.yaml lookup**

Find:
```markdown
## Step 2: Read CV content

```bash
cat /Users/zall/interviews/cv_master_content.md
```
```

Replace with:
```markdown
## Step 2: Read user config and CV content

```bash
python3 -c "
import yaml
d = yaml.safe_load(open('config/user.yaml'))
u = d['user']
print('NAME:', u['name'])
print('EMAIL:', u['email'])
print('LINKEDIN:', u['linkedin_url'])
print('RESUME_PDF:', u['resume_pdf_path'])
print('CV_PATH:', d['cv_path'])
"
```

Then read the CV:
```bash
python3 -c "import yaml; print(yaml.safe_load(open('config/user.yaml'))['cv_path'])" | xargs cat
```

Capture: `name`, `email`, `linkedin_url`, `resume_pdf_path`, `cv_path`, and the CV text.
```

- [ ] **Step 3: Replace hardcoded fixed fields JSON in Step 4**

Find the entire JSON block under "### Fixed fields (always the same):":
```json
{
  "first_name": "Aleksandr",
  "last_name": "Zalesov",
  ...
  "resume_path": "/Users/zall/interviews/ALEKSANDR_ZALESOV-CV-05.2026.pdf",
  ...
}
```

Replace with:
```markdown
Populate the fixed fields from the values read in Step 2:
```json
{
  "first_name": "<first word of name from user.yaml>",
  "last_name": "<remaining words of name from user.yaml>",
  "full_name": "<name from user.yaml>",
  "email": "<email from user.yaml>",
  "phone": "",
  "linkedin_url": "<linkedin_url from user.yaml>",
  "resume_path": "<resume_pdf_path from user.yaml>",
  "years_of_experience": "<infer from CV>",
  "work_authorization": "<infer from CV locations/nationality>",
  "willing_to_relocate": "<based on work_style.willing_to_relocate in user.yaml>",
  "salary_expectation": "",
  "how_did_you_hear": "Job board",
  "start_date": "Immediately / 2 weeks notice"
}
```
```

- [ ] **Step 4: Replace hardcoded Telegram .env path in Step 6**

Find:
```
env_file = Path.home() / '.hermes' / 'profiles' / 'interviewprep' / '.env'
```
Replace with:
```
env_file = Path('hermes-profile') / '.env'
```

- [ ] **Step 5: Replace remaining personal fields in fixed fields JSON**

In the existing fixed fields JSON (Step 4 of the skill), find and remove/replace these hardcoded personal values that Step 3 may not have fully addressed:

Find:
```json
  "location": "Malaga, Spain",
```
Replace with:
```json
  "location": "<location from CV or leave blank>",
```

Find:
```json
  "country": "Spain",
```
Replace with:
```json
  "country": "<country from user.yaml locations[0].country or CV>",
```

Find:
```json
  "website_url": "https://zall.dev",
```
Replace with:
```json
  "website_url": "<personal website URL — infer from CV or leave blank>",
```

Find:
```json
  "work_authorization": "No — requires work permit / visa sponsorship (EU citizen, based Spain/Germany)",
```
Replace with:
```json
  "work_authorization": "<infer from CV — citizenship, visa status, work permit needs>",
```

- [ ] **Step 6: Replace absolute script path in Step 5**

Find (in Step 5 of the skill, the filler script command):
```bash
python3 /Users/zall/interviews/scripts/apply_job_filler.py \
```
Replace with:
```bash
python3 scripts/apply_job_filler.py \
```

- [ ] **Step 7: Remove remaining personal name in error handling**

Find (in Error Handling section):
```markdown
so Zall can fill them manually
```
Replace with:
```markdown
so the user can fill them manually
```

- [ ] **Step 8: Verify no personal names or absolute paths remain**

```bash
grep -n "Zall\|zall\|Aleksandr\|zallesov\|/Users/\|Malaga\|zall\.dev\|Spain/Germany\|interviewprep" skills/apply-job/SKILL.md
# Expected: no output
```

- [ ] **Step 9: Commit**

```bash
git add skills/apply-job/SKILL.md
git commit -m "feat: generalize apply-job skill — read user identity from config/user.yaml"
```

---

## Chunk 2: New Skills

### Task 4: Create check-auth skill

**Files:**
- Create: `skills/check-auth/SKILL.md`

- [ ] **Step 1: Create the skill file**

Create `skills/check-auth/SKILL.md`:

```markdown
---
name: check-auth
description: Verify browser sessions for all active job board providers. Runs check_auth.py for each active provider and reports pass/fail. Triggered by "check auth", "re-authenticate", "/check-auth", or called from onboarding.
---

# Check Auth

## Trigger

Run when: "check auth", "re-authenticate", "check my sessions", `/check-auth`, or invoked from the onboarding skill.

## Execution Rules

- Run for every provider where `providers.<name>: true` in `config/user.yaml`.
- Report per provider: ✅ authenticated / ❌ needs login.
- For providers needing login: give exact instructions for the user to log in via the Chrome window, then suggest re-running this skill.
- Can be run at any time — safe to run repeatedly.

## Step 1: Read active providers

```bash
python3 -c "
import yaml
d = yaml.safe_load(open('config/user.yaml'))
active = [p for p, enabled in d['providers'].items() if enabled]
print(' '.join(active))
"
```

## Step 2: Run check_auth for each active provider

For each active provider name:

```bash
python3 scripts/providers/<provider>/check_auth.py http://localhost:9222
```

Capture exit code and any output. `AuthError` in output means ❌. Clean exit means ✅.

## Step 3: Report results

Print a summary like:

```
Auth check results:
  greenhouse  ✅ authenticated
  jobleads    ❌ needs login
  wellfound   ✅ authenticated
```

## Step 4: For each failed provider

Tell the user:

> Open the Chrome window (run `~/start-chrome.sh` if not running), navigate to <provider login URL>, log in manually, then run `/check-auth` again to verify.

Provider login URLs:
- **Greenhouse:** https://my.greenhouse.io/users/sign_in
- **JobLeads:** https://www.jobleads.com/login
- **Wellfound:** https://wellfound.com/login
- **Sprout:** https://app.usesprout.com/login

## Chrome Pre-Flight

Before running any check_auth:

```bash
curl -s http://localhost:9222/json/version | python3 -c "import sys,json; d=json.load(sys.stdin); print('Chrome OK:', d.get('Browser','unknown'))" 2>/dev/null || echo "NOT_RUNNING"
```

If `NOT_RUNNING`: tell user to run `~/start-chrome.sh` first.
```

- [ ] **Step 2: Commit**

```bash
git add skills/check-auth/SKILL.md
git commit -m "feat: add check-auth skill"
```

---

### Task 5: Create run-scraping-pipeline skill

**Files:**
- Create: `skills/run-scraping-pipeline/SKILL.md`

- [ ] **Step 1: Create the skill file**

Create `skills/run-scraping-pipeline/SKILL.md`:

```markdown
---
name: run-scraping-pipeline
description: Run job scraping for one or all active providers × one or all configured locations. Reads config/user.yaml for providers, locations, search_terms. Triggered by "run scraping", "scrape jobs", "run pipeline for greenhouse berlin", etc.
---

# Run Scraping Pipeline

## Trigger

- "run scraping" / "scrape jobs" → all active providers × all locations
- "run greenhouse berlin" / "run pipeline for greenhouse berlin" → greenhouse × berlin only
- "run all scrapers for spain" / "scrape jobs in spain" → all active providers × spain
- "run wellfound" → wellfound × all locations

## Execution Rules

- Do NOT ask for confirmation. Execute immediately.
- On `AuthError`: stop that provider/location combo, tell user to run `/check-auth` first.
- Report per run: scraped count / new after dedup / ingested / failures.

## Step 1: Chrome pre-flight check

```bash
curl -s http://localhost:9222/json/version | python3 -c "import sys,json; d=json.load(sys.stdin); print('OK')" 2>/dev/null || echo "NOT_RUNNING"
```

If `NOT_RUNNING`: tell user to run `~/start-chrome.sh` first. Do not proceed.

## Step 2: Read config

```bash
python3 -c "
import yaml, json
d = yaml.safe_load(open('config/user.yaml'))
active_providers = [p for p, enabled in d['providers'].items() if enabled]
locations = [loc['city'] for loc in d['locations']]
titles = ','.join(d.get('search_terms', []))
print(json.dumps({'providers': active_providers, 'locations': locations, 'titles': titles}))
"
```

## Step 3: Determine scope

Apply any overrides from the user's request:
- Specific provider mentioned → use only that provider (if active)
- Specific location/city mentioned → use only that location
- "all" → use all active providers × all locations

## Step 4: Run pipeline for each (provider, location) combination

For each combination:

```bash
python3 scripts/scraping_pipeline.py \
  --provider <provider> \
  --location <city> \
  --titles "<comma-separated search_terms>"
```

Capture stdout. Parse `[pipeline]` log lines for counts.

## Step 5: Report results

After all runs complete, summarize:

```
Scraping complete:
  greenhouse × Berlin: 42 scraped, 8 new, 8 ingested (0 enrich failures)
  jobleads × Berlin: 17 scraped, 3 new, 3 ingested (1 enrich failure)
  ...
Total: N new jobs added. Dashboard: http://localhost:3000
```

## On AuthError

If a run exits with `AuthError`:

> Session expired for <provider>. Run `/check-auth` to verify and re-login, then try scraping again.

Stop that provider's runs but continue with others.

## Examples

```
"run scraping"                → all active providers × all configured locations
"run greenhouse berlin"       → greenhouse × Berlin only
"run all scrapers for spain"  → all active providers × Spain
"run wellfound"               → wellfound × all configured locations
```
```

- [ ] **Step 2: Commit**

```bash
git add skills/run-scraping-pipeline/SKILL.md
git commit -m "feat: add run-scraping-pipeline skill"
```

---

### Task 6: Create add-job-by-url skill

**Files:**
- Create: `skills/add-job-by-url/SKILL.md`

**Context:** Users paste a job URL in chat (Hermes CLI, Telegram, or dashboard). The skill deduplicates by URL, ingests a minimal ShallowJob, then calls `enrich_job` and `sanity_check_job` from the existing pipeline. Uses the same scripts as the automated pipeline.

- [ ] **Step 1: Create the skill file**

Create `skills/add-job-by-url/SKILL.md`:

```markdown
---
name: add-job-by-url
description: Add a single job by URL. Deduplicates, ingests, enriches, and sanity-checks. Works from Hermes chat, Telegram, or dashboard. Triggered when user provides a job posting URL.
---

# Add Job by URL

## Trigger

Any message that contains a job posting URL (e.g., `https://boards.greenhouse.io/...`, `https://wellfound.com/jobs/...`, `https://jobleads.com/...`, any `https://` URL that looks like a job posting).

Also triggered by: "add this job", "track this job", "add job by url".

## Execution Rules

- Execute immediately without asking for confirmation.
- Do NOT enrich if duplicate is detected.
- Uses the same pipeline functions as the automated scraper — do not reimplement.

## Step 1: Read db_path from config

```bash
python3 -c "import yaml; d=yaml.safe_load(open('config/user.yaml')); print(d.get('db_path','jobs.db'))"
```

## Step 2: Check for duplicate

```bash
python3 -c "
import sqlite3, sys
db = '<db_path>'
url = '<url>'
con = sqlite3.connect(db)
row = con.execute('SELECT id FROM jobs WHERE url=?', (url,)).fetchone()
if row:
    print(f'DUPLICATE:{row[0]}')
else:
    print('NEW')
con.close()
"
```

If `DUPLICATE:<id>`: report "Already tracked as job ID N" and stop.

## Step 3: Ingest minimal job record

```bash
python3 -c "
import sys, json
sys.path.insert(0, '.')
from scripts.pipeline.types import ShallowJob
from scripts.pipeline.ingest import ingest_jobs
url = '<url>'
job = ShallowJob(
    provider='manual',
    title='',
    company='',
    url=url,
    location='',
    country=None,
    dedup_key=url,
    posting_date=None,
    salary_raw=None,
)
ids = ingest_jobs([job], db_path='<db_path>')
print(ids[0])
"
```

Capture the job_id.

## Step 4: Enrich the job

```bash
python3 -c "
import sys
sys.path.insert(0, '.')
from scripts.pipeline.enrich_job import enrich_job
result = enrich_job(<job_id>, db_path='<db_path>')
print('success:', result.success)
if result.error:
    print('error:', result.error)
"
```

If enrichment fails: report error and stop (job is still in DB with status `enrich_failed`).

## Step 5: Sanity check

```bash
python3 -c "
import sys
sys.path.insert(0, '.')
from scripts.pipeline.sanity_check_job import sanity_check_job
result = sanity_check_job(<job_id>, db_path='<db_path>')
print('success:', result.success, 'data:', result.data)
"
```

## Step 6: Report result

Read the job record and report:

```bash
python3 -c "
import sqlite3, json
con = sqlite3.connect('<db_path>')
con.row_factory = sqlite3.Row
row = con.execute('SELECT id, title, posted_company_name, status, url FROM jobs WHERE id=?', (<job_id>,)).fetchone()
print(json.dumps(dict(row)))
con.close()
"
```

Report to user:
```
✅ Job added: #<id>
  Title: <title>
  Company: <company>
  Status: <status>
  Dashboard: http://localhost:3000
```

If `status = sanity_failed`: add "⚠️ Sanity check failed — job may not match your profile. Check dashboard for details."
```

- [ ] **Step 2: Commit**

```bash
git add skills/add-job-by-url/SKILL.md
git commit -m "feat: add add-job-by-url skill"
```

---

### Task 7: Create onboarding skill

**Files:**
- Create: `skills/onboarding/SKILL.md`

**Context:** Walks a new user through full setup: CV, user identity, locations, work style, search terms, provider signup, Chrome/auth verification. Writes everything to `config/user.yaml`. References `check-auth` skill at the end.

- [ ] **Step 1: Create the skill file**

Create `skills/onboarding/SKILL.md`:

```markdown
---
name: onboarding
description: First-time setup wizard for JobLandAgent. Asks for CV, user identity, locations, work style, search terms, and provider accounts. Writes config/user.yaml. Runs check-auth at the end. Triggered by "/onboarding", "set up joblandagent", or "I'm new here".
---

# Onboarding

## Trigger

`/onboarding`, "set up", "set up joblandagent", "I'm new here", "help me get started"

## Execution Rules

- Ask questions one at a time. Wait for each answer before proceeding.
- Write all collected values to `config/user.yaml` at the end (Step 8), not incrementally.
- Be conversational and encouraging. This is a guided wizard, not a form.

---

## Step 1: Welcome

Say:

> Welcome to **JobLandAgent**! 👋
>
> I'm your autonomous job search assistant. Here's what I do:
> 1. **Scrape** job boards (Greenhouse, JobLeads, Wellfound, Sprout) on schedule
> 2. **Enrich** each listing: extract salary, apply URL, full description
> 3. **Sanity-check** postings against your CV — filter out mismatches
> 4. **Research** promising companies: funding, Glassdoor, red flags, fit score
> 5. **Fill** application forms in Chrome — you review and submit
>
> Let's get you set up. I'll ask a few questions and write your config file.

---

## Step 2: Ask for CV path

Ask:

> Where is your CV in markdown format? (e.g. `~/cv.md` or `/Users/you/docs/cv.md`)
> If you don't have one yet, I can help you create it from a PDF or paste.

Accept the path. Verify the file exists:

```bash
test -f "<cv_path>" && echo "EXISTS" || echo "NOT_FOUND"
```

If `NOT_FOUND`: tell user to create/copy it first, then come back. If `EXISTS`: copy to `config/cv.md`:

```bash
cp "<cv_path>" config/cv.md
```

---

## Step 3: Ask for user identity

Ask:

> What's your full name?

Then:

> Your email address?

Then:

> Your LinkedIn profile URL? (e.g. `https://linkedin.com/in/yourhandle`)

Then:

> Path to your resume PDF? (used for form uploads, e.g. `~/resume.pdf`)

Accept each answer. Verify the PDF exists:

```bash
test -f "<resume_pdf_path>" && echo "EXISTS" || echo "NOT_FOUND"
```

Copy PDF to `config/resume.pdf` if path differs from `config/resume.pdf`.

---

## Step 4: Ask for target locations

Ask:

> Which cities or regions are you targeting for jobs? (You can list multiple, e.g. "Berlin, Barcelona, London")
>
> For each location I'll need:
> - City name
> - Country name
> - Country code (ISO 3166-1 alpha-2, e.g. DE, ES, GB)

Collect all locations. Format as a list of dicts.

---

## Step 5: Ask for work style

Ask:

> What's your work style preference?
> - **Remote** — fully remote only
> - **Hybrid** — flexible (some days in office)
> - **Onsite** — full-time in office

Then:

> Are you willing to relocate? (yes/no)

Map answer to `preferred: remote | hybrid | onsite` and `willing_to_relocate: true | false`.

---

## Step 6: Infer and confirm search terms

Read the CV content:

```bash
cat config/cv.md
```

Using the CV content, infer 4–6 relevant job titles the user should search for. Show the list:

> Based on your CV, I suggest searching for these job titles:
> - Software Engineer
> - AI Engineer
> - Engineering Manager
> - Platform Engineer
>
> Edit this list if needed. Add or remove titles.

Wait for confirmation or edits.

---

## Step 7: Ask about job board accounts

Ask:

> Which job boards have you signed up for? (I'll only scrape boards where you have an account)
>
> - **Greenhouse** (my.greenhouse.io) — personalized "for you" feed
> - **JobLeads** (jobleads.com) — aggregator with salary filters
> - **Wellfound** (wellfound.com) — startup-focused
> - **Sprout** (usesprout.com) — EU-focused

If a user hasn't signed up for a board, show the signup URL and suggest they sign up.

Set `providers.<name>: true` for each confirmed board.

---

## Step 8: Write config/user.yaml

Write the collected values to `config/user.yaml`:

```bash
python3 -c "
import yaml

config = {
    'user': {
        'name': '<name>',
        'email': '<email>',
        'linkedin_url': '<linkedin_url>',
        'resume_pdf_path': 'config/resume.pdf',
    },
    'cv_path': 'config/cv.md',
    'locations': [
        {'city': '<city>', 'country': '<country>', 'country_code': '<code>'},
        # ... additional locations
    ],
    'work_style': {
        'preferred': '<remote|hybrid|onsite>',
        'willing_to_relocate': <True|False>,
    },
    'search_terms': [<confirmed titles list>],
    'providers': {
        'greenhouse': <True|False>,
        'jobleads': <True|False>,
        'wellfound': <True|False>,
        'sprout': <True|False>,
    },
    'db_path': 'jobs.db',
}

with open('config/user.yaml', 'w') as f:
    yaml.dump(config, f, default_flow_style=False, allow_unicode=True)
print('config/user.yaml written')
"
```

---

## Step 9: Verify Chrome and auth

Say:

> Now let's verify your browser sessions. Chrome must be running first.

Check Chrome:

```bash
curl -s http://localhost:9222/json/version | python3 -c "import sys,json; d=json.load(sys.stdin); print('OK')" 2>/dev/null || echo "NOT_RUNNING"
```

If `NOT_RUNNING`: tell user to run `~/start-chrome.sh`, wait for confirmation.

Then invoke the `check-auth` skill:

> Running auth checks for your active providers...

(Invoke check-auth skill here.)

---

## Step 10: Explain the system and close

Say:

> 🎉 Setup complete! Here's how to use JobLandAgent:
>
> | What | How |
> |---|---|
> | Scrape jobs | "run scraping" |
> | Add a specific job | Paste any job URL in this chat |
> | Research a job | "research job 42" |
> | Apply to a job | "apply to job 42" |
> | View dashboard | http://localhost:3000 (run `cd dashboard && npm run dev`) |
> | Re-check auth | "/check-auth" |
>
> Type **"run scraping"** to kick off your first pipeline run!
```

- [ ] **Step 2: Commit**

```bash
git add skills/onboarding/SKILL.md
git commit -m "feat: add onboarding skill"
```

---

## Chunk 3: README + Dashboard Title

### Task 8: Write README.md

**Files:**
- Create: `README.md`

- [ ] **Step 1: Create README.md at repo root**

```markdown
# JobLandAgent

An autonomous job search assistant for software engineers. Scrapes job boards, enriches listings with AI, scores them against your CV, and fills application forms in Chrome — you review and submit.

![Python](https://img.shields.io/badge/python-3.11+-blue) ![Node](https://img.shields.io/badge/node-20+-green) ![License](https://img.shields.io/badge/license-MIT-lightgrey)

---

## How it works

1. **Scrape** — Playwright pulls jobs from Greenhouse, JobLeads, Wellfound, and Sprout into a local SQLite DB
2. **Enrich** — AI extracts salary, apply URL, full description, and remote status from each posting
3. **Sanity-check** — AI scores each job against your CV, filtering out mismatches by seniority, location, and work style
4. **Research** — Deep company analysis: funding, Glassdoor, red flags, fit score
5. **Apply** — AI fills application forms in a visible Chrome window — you review and click Submit

---

## Prerequisites

- Python 3.11+
- Node 20+
- [Hermes AI](https://hermes-agent.com) — install via their docs
- Google Chrome

---

## Setup

**1. Clone and install**

```bash
git clone https://github.com/<you>/joblandagent
cd joblandagent
pip install -r requirements.txt
cd dashboard && npm install && cd ..
```

**2. Configure**

```bash
cp config/user.yaml.example config/user.yaml
# Copy your CV as markdown:
cp ~/your-cv.md config/cv.md
```

**3. Set up Hermes profile**

```bash
# Point Hermes at the profile in this repo:
hermes --profile ./hermes-profile
# Then edit hermes-profile/config.yaml:
#   model.api_key: <your LLM provider API key>
#   (skills.external_dirs is already set to ["../skills"])
```

**4. Set up Telegram (optional but recommended)**

Follow [Hermes Telegram bot setup](https://hermes-agent.com/docs/telegram). Enables job notifications and lets you add jobs by pasting URLs in Telegram chat.

**5. Start Chrome**

```bash
cp start-chrome.sh ~/start-chrome.sh && chmod +x ~/start-chrome.sh
~/start-chrome.sh
# Launches Chrome on localhost:9222 with a persistent profile
```

**6. Run onboarding**

```bash
hermes --profile ./hermes-profile
# Then type:
/onboarding
```

Hermes walks through the rest of setup: asking for your locations, CV, search terms, and provider accounts.

---

## Starting the dashboard

```bash
cd dashboard && npm run dev
# Opens http://localhost:3000
```

---

## Usage

| Action | How to trigger |
|---|---|
| Scrape jobs | "run scraping" in Hermes |
| Scrape specific source | "run greenhouse berlin" |
| Add job by URL | Paste any job URL in Hermes or Telegram |
| Research a job | "research job 42" |
| Apply to a job | "apply to job 42" — fills form, does NOT submit |
| Check auth sessions | "/check-auth" |
| Re-run onboarding | "/onboarding" |

---

## Supported job boards

| Board | Type | Notes |
|---|---|---|
| [Greenhouse](https://my.greenhouse.io) | Feed-based | Personalised "for you" feed |
| [JobLeads](https://jobleads.com) | Feed-based | Aggregator with salary filters |
| [Wellfound](https://wellfound.com) | UI-based | Startup-focused |
| [Sprout](https://usesprout.com) | UI-based | EU-focused |

---

## Configuration reference

All user config lives in `config/user.yaml` (copy from `config/user.yaml.example`):

| Key | Purpose |
|---|---|
| `user.name`, `user.email`, etc. | Identity for application forms |
| `cv_path` | Path to your CV in markdown |
| `locations` | List of `{city, country, country_code}` dicts |
| `work_style.preferred` | `remote` \| `hybrid` \| `onsite` |
| `search_terms` | Job titles to search and filter by |
| `providers` | Enable/disable each job board |
| `db_path` | SQLite DB file path |

---

## Supported locations

Any city can be added to `config/user.yaml`. Each location needs `city`, `country`, and `country_code` (ISO 3166-1 alpha-2). Feed-based scrapers (Greenhouse, JobLeads) use the `country_code` for a country-level search. UI-based scrapers (Wellfound, Sprout) search by `city` string directly.

---

## Re-authenticating

If a job board session expires, type `"check auth"` in Hermes or run `/check-auth`. You'll be told which providers need login and shown the login URL for each.

---

## Contributing

Adding a new job board requires implementing two files:
- `scripts/providers/<name>/check_auth.py` — verify browser session
- `scripts/providers/<name>/scrape_jobs.py` — scrape and return `list[ShallowJob]`

See existing providers for the interface contract.
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: add README for JobLandAgent open-source release"
```

---

### Task 9: Update dashboard title

**Files:**
- Modify: `dashboard/app/layout.tsx`

**Context:** The dashboard title is currently "AutoJobs" (line 19). Change to "JobLandAgent".

- [ ] **Step 1: Update the title**

In `dashboard/app/layout.tsx`, find:
```typescript
  title: "AutoJobs",
```

Replace with:
```typescript
  title: "JobLandAgent",
```

- [ ] **Step 2: Verify change**

```bash
grep "title" dashboard/app/layout.tsx | head -5
# Expected: title: "JobLandAgent",
```

- [ ] **Step 3: Commit**

```bash
git add dashboard/app/layout.tsx
git commit -m "chore: rename dashboard title AutoJobs → JobLandAgent"
```
