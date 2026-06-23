# JobLandAgent — Agent Context

Autonomous job search assistant. Scrapes boards → enriches → screens against CV → researches companies → fills applications in Chrome. You review and click Submit.

---

## Project Layout

```
skills/                   Hermes skills (all skills live here)
scripts/
  scraping_pipeline.py    Top-level pipeline orchestrator
  add_job_by_url.py       Ingest a single job URL
  enrich_job.py           Enrich one job via CDP
  enrich_jobs_batch.py    Bulk enrichment
  pipeline/               Reusable pipeline modules
    dedup.py              Deduplicate by dedup_key
    ingest.py             Write ShallowJob list → DB
    enrich_job.py         CDP enrichment module
    screen_job.py         Screen one job via LLM
    screen_jobs_batch.py  Parallel batch screening
    notify.py             Daily digest via Telegram
    types.py              Shared types (ShallowJob, etc.)
  providers/
    greenhouse/           Feed-based (personalized feed)
    jobleads/             Feed-based aggregator w/ salary filters
    wellfound/            UI-based (startup-focused)
    sprout/               UI-based (EU-focused)
    hirify/               Saved-filter UI (IT/Digital)
    csvfeed/              CSV import provider
    _shared/              Shared provider utilities
config/
  user.yaml               Personal config (gitignored — copy from user.yaml.example)
  cv.md                   Your CV in markdown (gitignored)
  user.yaml.example       Template
tests/                    pytest suite
jobs.db                   SQLite database (gitignored at runtime)
config.yaml               Hermes agent config (model: deepseek-v4-flash)
SOUL.md                   Agent persona + operational rules
```

---

## Key Paths

| Resource | Path |
|---|---|
| User config | `config/user.yaml` |
| CV | `config/cv.md` |
| Database | `jobs.db` (override via `db_path` in config) |
| Skills | `skills/` |
| Pipeline scripts | `scripts/` |
| Providers | `scripts/providers/<name>/` |
| Pipeline modules | `scripts/pipeline/` |

---

## Model

Default: `deepseek-v4-flash` via `https://api.deepseek.com/v1`
Requires: `DEEPSEEK_API_KEY` env var

---

## Chrome CDP

All scraping and enrichment requires Chrome at `http://localhost:9222`.

Pre-flight:
```bash
curl -s http://localhost:9222/json/version | grep -q "{" && echo "OK" || echo "NOT_RUNNING"
```

If `NOT_RUNNING`: tell user to run `bash start-chrome.sh`. Do not proceed.

Verify correct profile is loaded:
```bash
ps -Ao pid,command | grep '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' | grep -- '--remote-debugging-port=9222' | grep -v grep
```
Expected: `--user-data-dir=/Users/zall/.hermes/profiles/joblandagent-dev/.chrome-profile`

### ALL CHROME OPERATIONS MUST BE VISIBLE

**The user watches the Chrome window.** Every CDP page MUST call `page.bring_to_front()` immediately after `ctx.new_page()` — before any navigation. No invisible/background tabs.

- After `page = ctx.new_page()`, call `page.bring_to_front()` before `page.goto()`.
- `page.close()` at end is fine.
- Exception: only skip if user explicitly asks for quiet/no-visual mode.

---

## Pipeline Scripts

```bash
# Scrape all active providers
python3 scripts/scraping_pipeline.py

# Scrape one provider
python3 scripts/scraping_pipeline.py --provider <name>
# providers: greenhouse | jobleads | wellfound | sprout | hirify | csvfeed

# Add a single job by URL
python3 scripts/add_job_by_url.py --url <url>

# Enrich
python3 scripts/enrich_job.py --job-id <id>
python3 scripts/enrich_jobs_batch.py --job-ids <ids>

# Screen (batch preferred)
python3 -c "
import sys; sys.path.insert(0, 'scripts')
from pipeline.screen_jobs_batch import screen_jobs_batch
ok, fail = screen_jobs_batch([42, 43], max_workers=5)
print(f'{len(ok)} ok, {len(fail)} failed')
"
```

Each provider exposes exactly two files:
- `scripts/providers/<name>/check_auth.py` — verify session
- `scripts/providers/<name>/scrape_jobs.py` — return `list[ShallowJob]`

---

## Skills

| Skill | When to use |
|---|---|
| `onboarding` | First-time setup |
| `check-auth` | Before scraping; when provider login expires |
| `job-pipeline` | Run scraping pipeline; recover from failures |
| `enrich-job` | Enrich jobs by visiting URLs in Chrome |
| `screen-job` | Screen a job against CV — produce verdict + score |
| `job-research` | Deep research on a specific job/company |
| `add-job-by-url` | User provides a job URL to track |
| `apply-job` | User says "apply to job N" (interactive, never clicks Submit) |
| `run-scraping-pipeline` | Triggered by natural-language scraping requests |

---

## Database Schema

SQLite at `jobs.db`. Key tables:

**`jobs`** — one row per posting
- `pipeline_status`: `new` | `enriched` | `enrich_failed` | `screened` | `skip`
- `user_status`: `applied` | `rejected` | `offer` | `withdrawn` | NULL
- `research_status`: `researched` | NULL
- `status`: legacy field, still used in some queries

**`job_assessments`** — LLM screening output (1:1 with jobs)
- `relevance_score` (0–100), `apply_verdict`, `red_flag_scan`, `seniority_fit`, `tech_stack_fit`, `remote_eligibility`

**`company_research`** — company deep-research
- `trustworthiness_score`, `glassdoor_summary`, `funding_summary`, `risk_news`

**`companies`** — normalized company records
**`applications`** — draft/submitted application tracking
**`agent_commands`** — async command queue (research, enrich triggered via dashboard)

Key queries:
```sql
-- Jobs needing enrichment
SELECT id, url FROM jobs WHERE pipeline_status = 'new' AND description IS NULL;

-- Jobs needing screening
SELECT id FROM jobs WHERE pipeline_status = 'enriched';

-- Top screened jobs
SELECT j.id, j.title, j.posted_company_name, a.apply_verdict, a.relevance_score
FROM jobs j JOIN job_assessments a ON a.job_id = j.id
ORDER BY a.relevance_score DESC;

-- Research queue
SELECT j.id, j.title FROM jobs j
WHERE j.pipeline_status = 'screened' AND j.research_status IS NULL;
```

---

## DB Write Rules

**Never write raw SQL to the database** except:
1. `status='running'` update in job-research Step 1
2. `db_write_research.py` in job-research Step 3
3. Explicit user instruction

Always use the pipeline helper scripts for writes. Raw SQL produces corrupted state (missing assessments, botched lifecycle).

---

## Job Status Lifecycle

```
Scrape → new
  → enrich → enriched | enrich_failed
  → screen → screened
  → research → research_status = 'researched'
  → apply → user_status = 'applied'
```

---

## Dashboard

Moved to `../dashboard/` (sibling dir in the `joblandagent` monorepo). Separate dev/deploy cycle —
no longer started or referenced from agent skills. See `../dashboard/README.md`.

---

## Codebase Rules

- Scripts: `scripts/`. No standalone scripts in project root.
- Provider scrapers: `scripts/providers/<name>/scrape_jobs.py`. No `scrape_<provider>.py` in `scripts/` root.
- Skills: `skills/`. Never `hermes-profile/skills/` or `tmp/skills/`.
- All providers run via `scripts/scraping_pipeline.py` — never call provider scripts directly.
- Scrapers return all jobs as `pipeline_status='new'` — no filtering at scrape time.
- Do NOT modify `skills/` or `scripts/` files unless explicitly asked. Write throwaway scripts in `tmp/` instead.

---

## Temporary Files

Use `tmp/` for any one-off scripts, SQL, data dumps. Never litter project root.

---

## What NOT to Commit

See `.gitignore`. Key exclusions:
- `jobs.db`, `*.db-*`, backups
- `config/user.yaml`, `config/cv.md` (personal data)
- `.env` (API keys)
- Personal CV/PDF files, research outputs, one-off scripts

---

## Tests

```bash
pytest tests/
```

Test structure mirrors `scripts/`: `tests/pipeline/`, `tests/providers/`, `tests/e2e/`.
