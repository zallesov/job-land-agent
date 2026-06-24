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
    ingest.py             Write ShallowJob list → PocketBase
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
.env                      PocketBase + model credentials (gitignored)
config.yaml               Hermes agent config (model: deepseek-v4-flash)
SOUL.md                   Agent persona + operational rules
```

---

## Key Paths

| Resource | Path |
|---|---|
| User config | `config/user.yaml` |
| CV | `config/cv.md` |
| Database | Remote PocketBase via `POCKETBASE_URL` in `.env` |
| Schema/migrations | `../db/` |
| PocketBase client | `scripts/pb_client.py` |
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

## Database

All job data lives in remote PocketBase (`POCKETBASE_URL` in `.env`), not SQLite. The `jobs.db` file is legacy and must not be used for active job storage.

Schema and migrations live in `../db/`. Until the MCP server owns database access, agent scripts use `scripts/pb_client.py`:

```python
from scripts.pb_client import get_pb

pb = get_pb()
jobs = pb.get_list("jobs", "pipeline_status='new' && description=''", sort="-created_at")
```

Key collections:

**`jobs`** — one record per posting
- `pipeline_status`: `new` | `enriched` | `enrich_failed` | `screened` | `skip`
- `user_status`: `applied` | `rejected` | `offer` | `withdrawn` | empty
- `research_status`: `researched` | empty
- `status`: legacy field, still present for compatibility

**`job_assessments`** — LLM screening output linked to `jobs`
- `relevance_score` (0-100), `apply_verdict`, `red_flag_scan`, `seniority_fit`, `tech_stack_fit`, `remote_eligibility`

**`companies`** — normalized company records

**`company_research`** — deep research linked to `companies`
- `trustworthiness_score`, `glassdoor_summary`, `funding_summary`, `risk_news`

**`agent_commands`** — async command queue for dashboard-triggered work

**`events`** — append-only event log

**`pipeline_runs`** — scraping/pipeline run tracking

**`interviews`** — interview process tracking

---

## DB Write Rules

Use the pipeline helper scripts for writes. When a direct database read/write is unavoidable, use `scripts/pb_client.py` (`from scripts.pb_client import get_pb`) and PocketBase collection names. Do not use SQLite, raw SQL, `sqlite3 jobs.db`, or `from scripts.db import`.

Ask before writing to PocketBase unless the user explicitly requested the write.

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

Use `tmp/` for any one-off scripts, PocketBase maintenance snippets, or data dumps. Never litter project root.

---

## What NOT to Commit

See `.gitignore`. Key exclusions:
- `.env` (PocketBase and API credentials)
- `jobs.db`, `*.db-*`, backups (legacy/runtime state)
- `config/user.yaml`, `config/cv.md` (personal data)
- Personal CV/PDF files, research outputs, one-off scripts

---

## Tests

```bash
pytest tests/
```

Test structure mirrors `scripts/`: `tests/pipeline/`, `tests/providers/`, `tests/e2e/`.
