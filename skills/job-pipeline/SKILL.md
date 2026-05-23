---
name: job-pipeline
description: Autonomous job hunting pipeline — Hermes supervisor, scrapers, SQLite, dashboard, and delegated agent workflows.
---

# Job Pipeline Skill

## 🚨 CRITICAL: Job Lifecycle State Machine

Every job in the pipeline follows EXACTLY three phases. NEVER skip a phase. NEVER auto-advance to the next phase without explicit user instruction.

```
                    ┌──────────────────┐
                    │     SCRAPE       │  (Phase 1)
                    │  status: new     │
                    └────────┬─────────┘
                             │ user says "research this job"
                             ▼
                    ┌──────────────────┐
                    │    RESEARCH      │  (Phase 2)
                    │ status: researched│
                    └────────┬─────────┘
                             │ user says "apply to this job"
                             ▼
                    ┌──────────────────┐
                    │     APPLY        │  (Phase 3)
                    │ status: applied  │
                    └──────────────────┘
```

### Phase 1: Scrape (status = `new`)
**Entry**: Job URL is provided (via scraper, manual paste, or Telegram).
**What happens**: Agent visits the URL, extracts raw listing data (description, location, salary, remote scope, company name, date). Enriches the `jobs` table metadata columns.
**Status must be**: `new`. NEVER change this.
**Exit**: User explicitly says "research this job" or equivalent.

### Phase 2: Research (status = `researched`)
**Entry**: User says "research job N" or "assess job N".
**What happens**: Full deep-dive — company website, LinkedIn, Glassdoor, Crunchbase, news. Cross-reference against Zall's CV/profile. Insert `company_research`, `job_assessments`.
**Research method**: Use the **headful browser** (browser_navigate / browser_click / browser_snapshot) for direct company/job site research. It handles JS-heavy ATS pages (Workday, Greenhouse, PeopleForce) better than Playwright scripts. Reserve Playwright scripts for Google searches where the headful browser triggers CAPTCHAs.
**Status changes**: `new` → `researched`. ONLY on explicit user instruction.
**Exit**: User says "apply to this job" or equivalent.

### Phase 3: Apply (status = `applied` / `apply_failed`)
**Entry**: User says "apply to job N".
**What happens**: Navigate to apply_url, detect form fields, fill from profile, submit.
**Status changes**: `researched` → `applied` or `apply_failed`.
**Exit**: Done.

### ⛔ What NOT to do (hallucination prevention):
- **"Re-scrape" / "fetch data" / "refresh"**: Only updates metadata columns. Do NOT touch `jobs.status`. Do NOT insert/update `job_assessments`. Do NOT insert/update `company_research`.
- **Auto-transition**: Never advance a job from `new` to `researched` without the user explicitly asking for research.
- **Status inventing**: Only use statuses `new`, `researched`, `applied`, `apply_failed`. Nothing else.
- **If unsure**: Ask the user which phase they want. Don't guess.

## Purpose

Operate and extend the autonomous job hunting pipeline. Hermes is the supervisor — it schedules scrapers, ingests results into SQLite, delegates intelligence tasks to agents (research, resume tailoring), and sends Telegram notifications. Scripts are tools. Agents are workers.

## Architecture

```
Hermes (supervisor, scheduler, router, notifier)
│
├── Daily Pipeline (cron, morning Europe/Madrid)
│   ├── Spawn scraper processes, monitor exit codes
│   ├── On failure: log, notify, continue with remaining providers
│   ├── Ingest successful artifacts → SQLite
│   ├── Light tagging (keyword-based in v1)
│   └── Send Telegram digest
│
├── Research Workflow (UI-triggered via agent_commands)
│   ├── Read job + company from SQLite
│   ├── Delegate to InterviewPrep agent (browser + web_search)
│   ├── Write company_research + job_assessments to SQLite
│   └── Send Telegram notification
│
└── Application Workflow (UI-triggered via apply-agent skill)
    ├── Read job + assessment from SQLite (jobs, job_assessments)
    ├── Load profile.json + resume PDF
    ├── Navigate to apply_url via browser tools
    ├── Detect form fields, map to profile, fill and submit
    ├── Handle captchas, file uploads, Lever location field, radio/checkbox quirks
    ├── Write to applications table (status: applied/failed/intervention)
    ├── Update jobs.status to 'applied' or 'apply_failed'
    └── Send Telegram notification
```

## Key Files

| File | Role |
|------|------|
| `scripts/db.py` | SQLite access layer — all tables, indexes, helpers |
| `scripts/scraping_pipeline.py` | Unified pipeline: `--provider <name>` runs scrape → dedup → ingest → enrich → screen inline |
| `scripts/providers/<name>/scrape_jobs.py` | Per-provider Playwright scraper (greenhouse, jobleads, wellfound, sprout, hirify) |
| `scripts/pipeline/enrich_job.py` | Enriches a job by ID — fetches description, company info |
| `scripts/pipeline/screen_job.py` | Screens a job by ID — produces `apply_verdict` + `relevance_score` |
| `scripts/telegram_notify.py` | Sends via `hermes send --to telegram` |
| `dashboard/` | Next.js 14 + better-sqlite3 — job list, detail pane, research trigger |
| `docs/plans/` | Implementation plans 00–07 |

## Provider Scrapers

### Greenhouse (current)
- Script: `outputs/jobleads_export/scrape_greenhouse_playwright_mcp.test.js`
- Method: Codex executes the scraper via its Playwright MCP server, using system Chrome with a persistent `userDataDir` so Greenhouse auth cookies survive across sessions.
- Codex skill: `/Users/zall/interviews/skills/greenhouse-daily-export/` (SKILL.md + `references/scrape.js`)
- Searches: Software Engineer, AI Engineer, Engineering Manager × Berlin Remote, Spain Remote
- Output: `outputs/greenhouse/runs/greenhouse_jobs_live_YYYY-MM-DD.json`
- Invocation: `codex exec --skip-git-repo-check "Run the greenhouse-daily-export skill. Save to outputs/greenhouse/runs/greenhouse_jobs_live_$(date +%Y-%m-%d).json"`
- Auth: Cookies persist via Playwright MCP's `userDataDir` at `~/.hermes/profiles/interviewprep/home/Library/Caches/ms-playwright/mcp-chrome-990c176`. If auth expires, the scraper detects the `/users/sign_in` redirect and fails fast with a clear error.
- Concurrency: Only one Codex/Playwright instance can own the Chrome profile at a time. Serialize cron runs (flock lockfile) to avoid profile-lock failures.

### Adding a new provider
1. Create `outputs/<provider>/runs/` directory
2. Write scraper script that outputs normalized JSON array
3. Normalized shape (see Plan 2): provider, url, applyUrl, company, title, description, location, country, remoteScope, datePosted, sourcePayload
4. Add to Hermes daily pipeline cron config

## Orphaned Command Recovery

`agent_commands` rows stuck in `pending` can accumulate. These are not retried automatically — they sit forever.

### Three Distinct Failure Modes

When the dashboard button sends a "Research" or "Apply" command, it spawns a detached Hermes process. Read the log file first to distinguish the root cause:

```bash
ls outputs/research-logs/job_<JOB_ID>_cmd_<CMD_ID>.log
cat outputs/research-logs/job_<JOB_ID>_cmd_<CMD_ID>.log
```

| Log pattern | Root cause | Action |
|---|---|---|
| Agent wrote a chat response (describes the job, suggests steps) | **Missing Hermes skill or external_dirs misconfig** — Hermes couldn't find the requested skill (`job-research` or `apply-job`). Check that the skill exists at `/Users/zall/interviews/skills/<SKILL_NAME>/SKILL.md` and that `skills.external_dirs` in config.yaml includes `/Users/zall/interviews/skills`. | Fix external_dirs, then re-trigger. Or run `research_job.py` directly, or use `delegate_task`. |
| Empty log or `file not found` | Hermes process crashed on spawn — the `interviewprep` binary or flags are broken | Check `$PATH`, verify `~/.local/bin/interviewprep` exists and is executable |
| Log shows `Could not resolve authentication method` | **Auth gap**: `research_job.py` uses `anthropic.Anthropic()` which reads `ANTHROPIC_API_KEY` from the environment, but the variable is not set on Zall's machine | Set the key, or swap the script to use Zall's local LM Studio endpoint instead |

### Detection

```sql
-- Find all pending research commands with their ages
SELECT ac.id, ac.payload_json, ac.created_at, j.title, j.url
FROM agent_commands ac
LEFT JOIN jobs j ON json_extract(ac.payload_json, '$.job_id') = j.id
WHERE ac.command_type = 'research_job' AND ac.status = 'pending'
ORDER BY ac.created_at;
```

### Recovery Procedure

1. **Check DB** for stale pending commands
2. **Check the log file** in `outputs/research-logs/` to determine the failure mode (see table above)
3. **If missing Hermes skill**: bypass the Hermes spawn — use this agent's `delegate_task` or the `job-research` skill directly. Do NOT fall back to `research_job.py` (deprecated, requires Anthropic API key).
4. **If auth gap**: either set `ANTHROPIC_API_KEY` in the environment, or swap the script to use the local LM Studio endpoint (`localhost:1234`, provider `lmstudio`, model `qwen3.6-27b-ud-mlx`). The script calls `anthropic.Anthropic().messages.create()` on line 110 — replace with an OpenAI-compatible local client.
5. **Rerun research** with the correct command-id so the script updates the agent_commands record:
   ```bash
   # Use the job-research skill (local browser, not Anthropic API):
   # Load job-research skill and follow its Step 1→2→3 with job_id=<JOB_ID> command_id=<COMMAND_ID>
   python3 /Users/zall/interviews/scripts/db_write_research.py --db jobs.db --job-id <JOB_ID> --command-id <COMMAND_ID> < /tmp/research_<JOB_ID>.json
   ```
6. Commands can run in parallel since they're independent — spawn as background processes with `notify_on_complete`
7. After completion, verify the command status changed:
   ```sql
   SELECT id, status, finished_at, result_json FROM agent_commands WHERE id = <COMMAND_ID>;
   ```

### ⚠️ Critical: command-id mapping

The `command_id` and `job_id` are NOT the same number. Always read from the DB to get the correct mapping:
```sql
SELECT id as command_id, payload_json FROM agent_commands WHERE command_type = 'research_job' AND status = 'pending';
-- payload_json contains {"job_id": <actual_job_id>}
```

### Dashboard → Hermes Bridge (how commands get created)

The dashboard's `/api/commands/route.ts` inserts an `agent_commands` row and spawns:

```
interviewprep --yolo --skills <SKILL_NAME> -z "<prompt>"
```

**Configured skill names (from route.ts `COMMAND_CONFIG`):**

| command_type | --skills value | Status |
|---|---|---|
| command_type | --skills value | Location | Status |
|---|---|---|---|
| `research_job` | `job-research` | `/Users/zall/interviews/skills/job-research/` | ✅ Resolved via external_dirs |
| `apply_job` | `apply-job` | `/Users/zall/interviews/skills/apply-job/` | ✅ Resolved via external_dirs |

**How Hermes resolves them:**

Both skills live in `/Users/zall/interviews/skills/`, registered via `config.yaml`:
```yaml
skills:
  external_dirs:
  - /Users/zall/interviews/skills
```

If a command still goes orphaned, check:
```bash
ls /Users/zall/interviews/skills/<SKILL_NAME>/SKILL.md         # does file exist?
grep external_dirs ~/.hermes/profiles/interviewprep/config.yaml # registered?
```

**Fix if still broken:**
  (a) Add the directory to `skills.external_dirs` in config.yaml
  (b) Or symlink: `ln -s /Users/zall/interviews/skills/<SKILL_NAME> ~/.hermes/profiles/interviewprep/skills/`
  (c) Or use `delegate_task` from this skill

## Auth Gap: research_job.py (DEPRECATED — DO NOT USE)

**This script is deprecated.** The `job-research` skill replaces it with local browser research. This section is retained for historical context only.

The `research_job.py` script on line 110 calls:
```python
client = anthropic.Anthropic()
```
This reads `ANTHROPIC_API_KEY` from the environment. On Zall's machine, this env var is **not set** (empty length 0).

**Evidence:** Commands 6, 8, 13 successfully ran the script but all failed with:
```
Could not resolve authentication method. Expected one of api_key, auth_token...
```

**Fix options:**
  (a) Set `ANTHROPIC_API_KEY` in the shell profile
  (b) Swap the script to use Zall's local LM Studio via OpenAI-compatible client (`localhost:1234`, no API key needed). The script already has LM Studio running with `qwen3.6-27b-ud-mlx`. Replace Anthropic client with:
      ```python
      from openai import OpenAI
      client = OpenAI(base_url="http://localhost:1234/v1", api_key="not-needed")
      ```

## Research Agent Contract

Hermes delegates research tasks to the InterviewPrep agent (not direct API calls).

### Research Method Selection

**Two tools, two contexts — choose based on the target:**

| Context | Tool | Why |
|---------|------|-----|
| Google search, generic web search | **Playwright via terminal()** | Browser tool triggers CAPTCHAs on Zall's IP |
| Direct company/job site (Workday, Greenhouse, PeopleForce, company website) | **Headful browser (browser_navigate)** | Handles JS-heavy ATS pages, login forms, dynamic filters; can inspect DOM via browser_console |

**Zall's preference:** For interactive research of a specific job/company, always prefer the headful browser tools. They give direct visual feedback and access to JS console for DOM inspection (`browser_console` with JavaScript expressions). Only fall back to Playwright scripts when searching Google or large-scale scraping.

### Pattern A: Headful Browser (for interactive research)

- `references/hermes-browser-infrastructure.md` — How the browser works, why you don't see a window, and how to verify it's running.
- `references/incubator-portfolio-mining.md` — Pattern for mining VC/incubator portfolio pages (Antler, YC, etc.) for remote engineering jobs: scrape, batch-create Kanban tickets, aggregate results.

**What "headful" actually means in Hermes**: Hermes runs the browser through a local **agent-browser** (headless Chromium) on your machine, NOT a cloud service. There is NO Browserbase, BrowserUse, or any cloud browser configured. The browser has full JS rendering, DOM interaction, click/scroll/type capabilities — but it runs headless locally, so **you will never see a Chrome window pop up on your machine**. This is the correct and intended behavior.

Verification that the browser is not cloud-based:
- Check env vars: `grep BROWSERBASE_API_KEY ~/.hermes/.env` — returns commented out (`#`)
- `npx agent-browser` launches locally; user agent shows `HeadlessChrome`

There are TWO distinct browser code paths:
1. **Research** -> agent-browser (headless local Chromium, no visible window)
2. **Apply** -> Playwright with `headless=False` (visible Chrome window, used by `apply-job` skill)

If you want to see what the research browser is doing visually, the agent can capture screenshots using `browser_vision()` and include them in its final report.

1. `browser_navigate(target_url)` — load the page
2. `browser_snapshot()` — parse interactive elements (ref IDs like @e10)
3. `browser_click(ref)` / `browser_type(ref, text)` — navigate the site
4. `browser_console(expression="...")` — extract data via JS (e.g., find link hrefs, read hidden elements)
5. `browser_get_images()` — if needed for visual analysis
6. `browser_vision(question="...", annotate=true)` — take a screenshot and analyze it visually, or to see what the page looks like

**Verification that the browser is working**: The `browser_navigate` response returns a page title, URL, and element snapshot. If you get these back with content, the browser loaded the page successfully. The `browser_console` tool can also return JS results (like DOM queries) to confirm rendering.

**When the external job aggregator (JobLeads, etc.) is stale:** always check the company's own career portal (Workday, Greenhouse, Lever). The role may have expired even if still listed on aggregators.

**Pro tip for Workday/ATS portals:** The "View Open Opportunities" link on careers pages often opens a new tab with the Workday/Greenhouse URL. Use `browser_console` to find the actual href — click event on `<a>` may open another tab and the snapshot won't show it. Pattern:
```js
document.querySelectorAll('a').forEach(a => {
  if (a.textContent.includes('View Open')) console.log(a.href);
});
```

### Pattern B: Playwright via terminal() (for search/scraping)

Use only when the target blocks headless browser automation or you need to avoid Google CAPTCHAs:

1. Write a temporary Python script using `playwright.async_api`
2. Execute it via `terminal()` with a generous timeout
3. Parse structured output from `page.evaluate()`

**Pattern for research scripts:**

```python
import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.set_extra_http_headers({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        })
        
        await page.goto("<target_url>")
        await page.wait_for_timeout(2000)
        
        # Extract structured data via evaluate()
        result = await page.evaluate("""() => {
            // Query selectors specific to the target page
            const items = document.querySelectorAll('...');
            return Array.from(items).map(el => el.textContent);
        }""")
        print(result)
        
        await browser.close()

asyncio.run(main())
```

**Key settings:**
- `headless=True` for batch/automated research
- Custom `User-Agent` to avoid bot detection
- `wait_for_timeout(2000)` after navigation for JS rendering
- Extract via `page.evaluate()` — returns JS values as Python data
- Write script to `/tmp/` and run with `python3 /tmp/script.py`
- Timeout: 20–30s for simple pages, 60s for heavy SPAs

**CAPTCHA mitigation:**
- Google CAPTCHAs appear on repeated queries. If you hit one, switch to a different search engine (DuckDuckGo) or target the specific job board directly (LinkedIn, PeopleForce, etc.)
- For Telegram channels: use `https://t.me/s/<channel_name>` (web preview) — it's accessible without authentication
- For job listings: go directly to the PeopleForce/Greenhouse/Lever URL from the job post

**Playwright setup** (one-time):
```bash
playwright install chromium
```
Already installed on Zall's machine. Chromium at Chromium Headless Shell 148.0.7778.96.

**Hermes passes:**
- `job_id` — row ID in jobs table
- `command_id` — agent_commands row ID to update status
- Path to `jobs.db`

**Agent workflow:**
1. LOAD: Read job + company from SQLite
2. CHECK: Existing company_research — skip company phase if cached
3. RESEARCH COMPANY: browser (website) + web_search (LinkedIn, Crunchbase, Glassdoor, news)
4. ASSESS JOB: Parse description, cross-reference with Zall's profile, score relevance/trust/fit
5. WRITE: Upsert company_research, insert job_assessments, update jobs.status='researched', write events
6. RETURN: Compact summary (verdict, relevance, trust, one-line) for Telegram notification

**Output schema** is defined in `scripts/research_job.py` `SCHEMA_DESCRIPTION` constant.

### ⚠️ Hard rule: command_id and job_id are distinct

The `command_id` (row in `agent_commands`) and `job_id` (row in `jobs`) are completely different numbers. When recovering a pending command, read both from the DB — never assume they match even if they're numerically close.

### ⚠️ HARD RULE: DB insert is NOT optional

The agent MUST write to SQLite as part of the research workflow — not after being reminded. Research without DB insertion is incomplete work. The sequence is:

1. RESEARCH → 2. WRITE TO DB → 3. REPORT TO USER

Never report research results to the user without first having written them to the database. The report is a summary of what was saved, not a substitute for saving.

### SQL Queries for Status & Command Updates

When research completes, the agent must update:

```sql
-- Insert company if not exists
INSERT OR IGNORE INTO companies (display_name, normalized_name, website_url, domain, linkedin_url)
VALUES ('Akvelon', 'akvelon', 'https://akvelon.com', 'akvelon.com', 'https://linkedin.com/company/akvelon');

-- Insert job (url is UNIQUE — INSERT OR IGNORE if already exists)
INSERT INTO jobs (url, provider, company_id, title, description, apply_url, location, country, remote_scope, status, source_payload_json)
VALUES ('<url>', '<provider>', <company_id>, '<title>', '<description>', '<apply_url>', '<location>', '<country>', '<remote_scope>', 'new', '<json>');

-- Insert company research
INSERT INTO company_research (company_id, researched_at, research_status, ...)
VALUES (<id>, datetime('now'), 'completed', ...);

-- Insert job assessment
INSERT INTO job_assessments (job_id, assessed_at, assessment_status, relevance_score, apply_verdict, ...)
VALUES (<id>, datetime('now'), 'completed', <score>, '<verdict>', ...);

-- Update job status to 'researched'
UPDATE jobs SET status='researched', updated_at=datetime('now') WHERE id=<job_id>;

-- Mark agent_command as completed
UPDATE agent_commands SET status='completed', finished_at=datetime('now'), result_json='<compact result>' WHERE id=<command_id>;

-- Log the event
INSERT INTO events (entity_type, entity_id, event_type, actor, event_json)
VALUES ('job', <job_id>, 'research_complete', 'interviewprep', '<json>');
```

`agent_commands` uses `finished_at` (not `completed_at`). The `company_research` uses `research_status='completed'` (not `'researched'`). The `job_assessments` uses `assessment_status='completed'` (not `'researched'`).

## Pitfalls

- **Ambiguous "re-scrape" means "refresh data, not status"**: When the user says "re-scrape" or "fetch the data again" for a job, they want the raw listing details refreshed (description, location, salary, company, etc.) — NOT a full research + assessment. Do NOT change `jobs.status` from its current value. Do NOT insert/update `job_assessments`. Only update metadata columns in the `jobs` table. The research/assessment pass is a separate, explicit action the user will request by name.

- **Agent reports research without DB writes**: Most common failure mode: agent researches a job, presents results to the user, but never inserts into SQLite. This means (a) the job isn't tracked for follow-up, (b) the dashboard shows nothing, (c) cron digests can't reference it. **Hard rule: DB write is MANDATORY before any user-facing report.** The report is a summary of what was saved, not a substitute for saving.
- **Direct API skips agent**: The current `research_job.py` calls `anthropic.Anthropic().messages.create()` directly — a single LLM call with no browser/web_search. This means company facts come from stale training data, not live research. The target is Hermes delegation to InterviewPrep agent.
- **Scraper runs via Codex, not Hermes directly**: The Greenhouse scraper is a Codex skill at `/Users/zall/interviews/skills/greenhouse-daily-export/` that spawns a Playwright MCP browser session. Hermes cannot invoke it as a headless CLI script — it must go through `codex exec`. This works for cron (Codex runs non-interactively with `--dangerously-bypass-approvals-and-sandbox`) but means two levels of agent indirection (Hermes → Codex → Playwright MCP). Auth persistence is handled by Playwright MCP's `userDataDir`.
- **Hermes only used for telegram**: Current implementation uses Hermes exclusively as a message sender (`hermes send`). The daily cron, scraper supervision, and research delegation aren't wired through Hermes yet — they're manual Python script runs.
- **User-owned fields are protected**: status, comment, current_interview_status must never be overwritten by scrapers or research. Ingestion respects this boundary.
- **Company research cache is permanent**: Once written, company_research rows are never refreshed. No staleness policy yet (discussed 90-day warning as future feature).
- **Keyword tag false positives from short keywords**: In `tag_new_jobs.py`, single-word or two-character keywords (e.g. `"em "`) match far too broadly — `"em "` hits "Software Engineer", "system", "problem", "team", causing 68% false positives. Rule: keywords must be at least 2 full words (e.g. `"engineering manager"`, `"eng manager"`) or anchored to relevant context. Tests for `classify()` should include a representative sample of real job titles to catch this before tagging production data.
- **Job description may be missing from the DOM**: Some job boards (FeverUp, some Greenhouse instances) redirect to application forms that never render the job description. In that case, estimate from the title and company profile, and note it in the assessment notes.
- **External aggregator may list expired jobs**: JobLeads, indeed, and other aggregators frequently list roles that are no longer on the company's own ATS. Always cross-reference against the company's career portal (Workday, Greenhouse, Lever, PeopleForce) before writing a full assessment. If the role is absent from the company's ATS but still on the aggregator, flag it as likely expired/filled in the assessment notes.
- **Dashboard research button creates orphaned commands (FIXED)**: Previously the dashboard spawned Hermes with `--skills job-research` but the skill wasn't in Hermes' library. Now both `job-research` and `apply-job` live under `/Users/zall/interviews/skills/` and are registered via `skills.external_dirs` in config.yaml. If orphaned commands still appear, verify the external_dirs config or symlink the skill into Hermes' skills directory.
- **research_job.py needs ANTHROPIC_API_KEY**: The script uses `anthropic.Anthropic()` which requires the env var to be set. If running from a minimal cron environment or without the key, the script fails silently (exit code 1, error in `agent_commands.error` column). Either set the key or replace the Anthropic client with an OpenAI-compatible local client pointed at LM Studio.
- **Kanban dispatch has no YAML concurrency key**: Adding `max_concurrency: 5` to the `kanban:` config section does NOT control how many tasks the dispatcher spawns. The dispatcher ignores it entirely. The ONLY mechanism is `hermes kanban dispatch --max N`. When `dispatch_in_gateway: true`, the gateway dispatches without `--max` and spawns ALL ready tasks simultaneously — catastrophic for 100+ tasks. For controlled dispatch, either set `dispatch_in_gateway: false` and dispatch manually with `--max 5`, or use a cronjob. See `references/kanban-mass-research.md`.

## Triggers

Use this skill when:
- Adding or debugging a job scraper
- Configuring Hermes cron for the daily pipeline
- Defining or modifying the research agent contract
- Troubleshooting ingestion, tagging, or notification failures
- Understanding how scrapers, ingestion, dashboard, and agents fit together
- Researching jobs manually via `delegate_task` when the pipeline script is blocked
- Debugging orphaned `agent_commands` stuck in `pending`
- Scheduling mass research (50+ jobs) via Kanban dispatcher — see `references/kanban-mass-research.md`

## References

- `references/manual-telegram-to-sqlite-workflow.md` — Step-by-step for ad-hoc job adds from Telegram messages: parse, check, insert, assess.
- `references/delegate-task-parallel-research.md` — Parallel research via `delegate_task` when `research_job.py` is blocked: full pattern with code, DB write sequence, and pitfalls.
- `references/pipeline-architecture-review.md` — Architecture analysis from May 18, 2026: gap between plans and implementation, Hermes supervisor model, research agent design.
- `references/job-fit-assessment-pattern.md` — Structured method for evaluating job postings against Zall's profile/CV: requirements table, verdict, next steps.
- `references/workday-ats-navigation.md` — Pattern for navigating Workday career portals with the headful browser: finding the ATS URL, searching, reading listings, handling expired-role detection.
- `references/dashboard-agent-bridge-debugging.md` — How the dashboard's Research/Apply buttons spawn Hermes, why commands go orphaned, and the three failure-mode triage table.
- `references/skill-location-convention.md` — Where skills live, external_dirs config, and migration history from `.codex/`.
- `references/ad-hoc-url-addition.md` — Workflow when user pastes a raw URL (not Telegram, not scraper): navigate → extract → insert company → insert job → create command → research.
- `references/hermes-browser-infrastructure.md` — How the browser works, headless vs headed, cloud provider status, **cookie hijacking pitfall**.
- `references/antler-incubator-companies.md` — Antler Berlin portfolio companies, URL filtering pattern, cohort structure.
- `references/explee-company-discovery.md` — Explee.com company discovery: search configs, DOM extraction, post-discovery workflow, per-job Telegram notification pattern.
- `references/kanban-mass-research.md` — Mass research (50–300+ jobs) via Kanban dispatcher: bulk task creation, concurrency control with `--max 5`, gateway dispatch pitfalls, and worker reclaim.
