# JobLandAgent Generalization Design

**Goal:** Make this repo a distributable, generic open-source project any technical user can clone and run as their own autonomous job search assistant.

**Architecture:** Three sub-projects implemented in order: (A) config generalization removes all personal data and makes the system configurable via `config/user.yaml`; (B) README provides a complete setup guide; (C) new skills (onboarding, check-auth, run-scraping-pipeline, add-job-by-url) plus SOUL.md rewrite give Hermes complete operational knowledge out of the box.

**Tech Stack:** Python 3.11+, Node 20+, SQLite, Hermes AI, Playwright, Next.js dashboard

---

## Sub-project A: Config Generalization

### New file: `config/user.yaml`

Gitignored. Copied from `config/user.yaml.example` during setup.

```yaml
# User identity — used by apply-job skill
user:
  name: "Your Name"
  email: "you@example.com"
  linkedin_url: "https://linkedin.com/in/yourhandle"
  resume_pdf_path: "config/resume.pdf"   # path to PDF for form uploads

# CV in markdown format — used by enrich-job and sanity-check-job Hermes skills
cv_path: "config/cv.md"

# Target job locations — any city or region name; country required for feed-based scrapers
locations:
  - city: "Berlin"
    country: "Germany"
    country_code: "DE"
  - city: "Barcelona"
    country: "Spain"
    country_code: "ES"

# Work style preference — used by sanity_check_job and job-research for scoring
work_style:
  preferred: "remote"          # remote | hybrid | onsite
  willing_to_relocate: false

# Job title search terms — used by Sprout and JobLeads scrapers
search_terms:
  - "Software Engineer"
  - "AI Engineer"
  - "Engineering Manager"
  - "Platform Engineer"

# Active job board providers
providers:
  greenhouse: true
  jobleads: true
  wellfound: true
  sprout: false

# SQLite database path (relative to repo root)
db_path: "jobs.db"
```

**Locations:** Any city or region. Each entry has `city`, `country`, and `country_code` (ISO 3166-1 alpha-2). `country_code` is needed by feed-based scrapers (Greenhouse, JobLeads) for URL parameters. UI-based scrapers (Wellfound, Sprout) use `city` as the search string directly.

**How locations flow to scrapers:** `LOCATION_PRESETS` dicts in the legacy scraper scripts are kept as-is for backward compatibility but are bypassed — the new `scrape_jobs(location, cdp_url)` interface receives a location dict from `user.yaml` directly. Each provider's `scrape_jobs.py` is updated to accept `location: dict` (with `city`, `country`, `country_code`) instead of a string key lookup.

**Work style** (`remote`/`hybrid`/`onsite`) is read from `user.yaml` by the `sanity-check-job` Hermes skill and `job-research` skill. The sanity check uses it as a hard filter when the posting is clearly incompatible (e.g., user wants remote-only and job is explicitly on-site only). The research skill uses it as a scoring dimension.

**`pipeline_config.json` is eliminated** — delete the file. `run-scraping-pipeline` skill reads `config/user.yaml` directly. Add `config/pipeline_config.json` to `.gitignore` as well to avoid accidental re-creation.

### How `search_terms` flows to scrapers

**Code changes required in Sub-project A (all part of the implementation plan):**

1. `scripts/scraping_pipeline.py` — add `--titles` CLI argument (comma-separated string) and `titles: list[str] | None = None` to `run()` signature
2. `run()` passes `titles` down to `scrape_jobs_fn(location, cdp_url, titles=titles)`
3. All four `scripts/providers/<provider>/scrape_jobs.py` — add `titles: list[str] | None = None` parameter to `scrape_jobs()`. When `titles` is provided, pass them to the underlying collector (or filter by them). Sprout keeps `DEFAULT_TITLES` as its internal fallback when `titles=None`.

The `run-scraping-pipeline` skill parses `search_terms` from `user.yaml` and passes them as a comma-separated string:

```bash
python3 scripts/scraping_pipeline.py \
  --provider greenhouse \
  --location berlin \
  --titles "Software Engineer,AI Engineer,Engineering Manager"
```

`argparse` splits on commas: `titles = [t.strip() for t in args.titles.split(",")]`.

### `hermes-profile/config.yaml`

Committed with:
- `api_key: ""` — user fills in their LLM provider key
- `skills.external_dirs: ["../skills"]` — relative to `hermes-profile/`, points to `skills/` at repo root. This is the correct committed value.
- No personal paths, no personal names, no live tokens

**Security action:** `hermes-profile/config.yaml` currently contains a live API key. Before committing, the key is removed (set to `""`). The current key is invalidated by the user separately.

### `check_auth.py` CLI entrypoint

Each `scripts/providers/<provider>/check_auth.py` gains a `__main__` block:

```python
if __name__ == "__main__":
    import sys
    check_auth(sys.argv[1] if len(sys.argv) > 1 else "http://localhost:9222")
```

This makes them callable as `python3 scripts/providers/greenhouse/check_auth.py [cdp_url]`.

### `requirements.txt`

Created at repo root. Minimum contents (exact versions pinned during implementation):
```
playwright
pyyaml
pytest
pytest-asyncio
```

### `.gitignore` additions

```
config/user.yaml
config/cv.md
config/resume.pdf
*.pdf
cv_master_content.md
ALEKSANDR_*.md
jobs.db
jobs.db-*
outputs/
tmp/
hermes-profile/auth.json
hermes-profile/.env
hermes-profile/.hermes_history
hermes-profile/cache/
hermes-profile/audio_cache/
hermes-profile/cron/output/
hermes-profile/home/
hermes-profile/.skills_prompt_snapshot.json
hermes-profile/.update_check
*.xlsx
*.backup-*
jobs_all.*
config/pipeline_config.json
```

### Skills archive

Move these from `skills/` to `tmp/skills/` (not deleted):

| Skill | Reason |
|---|---|
| `daily-pipeline` | Old version, superseded by `run-scraping-pipeline` |
| `job-scraping-pipeline` | Superseded by `run-scraping-pipeline` |
| `greenhouse-scraper` | Subsumed by orchestrator |
| `jobleads-scraper` | Subsumed by orchestrator |
| `greenhouse-daily-export` | XLSX-based |
| `jobleads-daily-export` | XLSX-based |
| `assess-jobs-due-diligence` | XLSX-based |
| `consolidate-jobs-workbook` | XLSX-based |
| `scrape-and-research-job` | Superseded by `add-job-by-url` |

Skills in `.codex.bak/` are already inactive — no action needed for those. Only skills in the active `skills/` directory are moved.

---

## Sub-project B: README

File: `README.md` at repo root.

### Sections

**Header:** Name `JobLandAgent`, one-line description, badge row (Python, Node, License).

**How it works:** Pipeline overview: scrape job boards → deduplicate → enrich with AI → sanity-check against CV → present in dashboard. Research step does deep company/role analysis. Apply step fills forms in Chrome without submitting.

**Prerequisites:**
- Python 3.11+
- Node 20+
- [Hermes AI](https://hermes-agent.com) — install via their docs
- Google Chrome

**Setup (numbered steps):**

1. **Clone and install**
   ```bash
   git clone https://github.com/<you>/joblandagent
   cd joblandagent
   pip install -r requirements.txt
   cd dashboard && npm install && cd ..
   ```

2. **Configure**
   ```bash
   cp config/user.yaml.example config/user.yaml
   # Edit config/user.yaml: fill in cv_path, locations, providers, user identity
   # Copy your CV as markdown to config/cv.md
   ```

3. **Set up Hermes profile**
   ```bash
   # Point Hermes at the profile in this repo:
   hermes --profile ./hermes-profile
   # Then edit hermes-profile/config.yaml:
   #   model.api_key: your LLM API key
   #   skills.external_dirs: ["../skills"]  ← relative to hermes-profile/
   ```

4. **Set up Telegram (optional but recommended)**
   Follow [Hermes Telegram bot setup](https://hermes-agent.com/docs/telegram). Telegram enables job notifications and lets you add jobs by pasting URLs in chat.

5. **Start Chrome**
   ```bash
   # start-chrome.sh is provided in the repo root — copy it to your home dir once:
   cp start-chrome.sh ~/start-chrome.sh && chmod +x ~/start-chrome.sh
   ~/start-chrome.sh
   # Launches Chrome on localhost:9222 with a persistent profile
   ```

   The script is committed at repo root (`start-chrome.sh`) with the correct CDP flags. Users copy it once.

6. **Run onboarding**
   ```bash
   hermes --profile ./hermes-profile
   ```
   Then type `/onboarding` — Hermes walks through the rest of setup.

**Starting the dashboard:**
```bash
cd dashboard && npm run dev
# opens http://localhost:3000
```

**Available processes:**

| Process | How to trigger |
|---|---|
| Scraping | "run scraping for greenhouse berlin" or "run all scrapers" |
| Enriching | Automatic after scraping; or "enrich job 42" |
| Research + scoring | "research job 42" |
| Add by URL | Paste any job URL to Hermes, Telegram, or dashboard URL field |
| Applying | "apply to job 42" — fills form in Chrome, does NOT submit |

**Supported job boards:** Greenhouse (MyGreenhouse personalised feed), JobLeads, Wellfound, Sprout

**Supported locations:** `berlin`, `spain` — adding new locations requires extending `LOCATION_PRESETS` in each scraper. PRs welcome.

**Re-authenticating:** If a job board session expires, type "check auth" in Hermes or run `/check-auth`.

---

## Sub-project C: SOUL.md + New Skills

### SOUL.md rewrite

The existing SOUL.md browser rules section (never launch a new browser, use CDP at localhost:9222, use native browser tools, tell user to run `~/start-chrome.sh` if Chrome is not running) is **preserved verbatim**. Only the identity paragraph and persona name change.

**Identity (replaces "You are InterviewPrep…" opening):**
```
You are JobLandAgent, an autonomous job search assistant.
You help users find, evaluate, and apply to software engineering jobs
by scraping job boards, enriching listings with AI, scoring them
against the user's CV, and managing the application pipeline.
```

**Always-known facts (appended to SOUL, not from memory):**
- User config: `config/user.yaml` — cv_path, locations, providers, search_terms, user identity
- Chrome must be running at `localhost:9222` before any scraping or auth (`~/start-chrome.sh`)
- Job status lifecycle (complete):
  ```
  listed → new → interesting → researching → researched → draft_ready
                                                         → not_interested
                                                         → applied → interviewing → rejected
                             → enrich_failed
                             → sanity_failed
                             → archived
  ```
- Dashboard: `http://localhost:3000` (`cd dashboard && npm run dev`)
- DB path from `config/user.yaml` (default: `jobs.db`)
- `skills.external_dirs` in `hermes-profile/config.yaml` must point to `../skills`

**Skill reference in SOUL:**

| Skill | Invoke when |
|---|---|
| `onboarding` | User is setting up for the first time |
| `check-auth` | Before scraping; when a provider login expires |
| `run-scraping-pipeline` | User asks to scrape (all providers or specific one/location) |
| `job-research` | User asks to research or score a specific job |
| `add-job-by-url` | User provides a job posting URL |
| `apply-job` | User says "apply to job N" |

### New skill: `onboarding`

**Trigger:** `/onboarding` or "set up joblandagent" or "I'm new here"

**Flow:**
1. Welcome message — explains what JobLandAgent does (scrape → enrich → score → apply)
2. Ask: path to CV file (markdown preferred) → copy to `config/cv.md`, write `cv_path` to `user.yaml`
3. Ask: full name, email, LinkedIn URL, path to PDF resume → write to `user.yaml` under `user:`
4. Ask: target locations — show supported presets (`berlin`, `spain`), warn that others need code changes → write to `user.yaml`
5. Read CV, infer job titles/roles using LLM → show list, ask user to confirm or edit → write `search_terms` to `user.yaml`
6. Ask: which job boards has user signed up for → show list with links → write `providers` to `user.yaml`
7. Explain: "Now let's verify your Chrome sessions for each active provider" → invoke `check-auth`
8. Explain all processes: scraping, enriching, research, add-by-URL, applying, dashboard URL
9. Close: "Type 'run scraping' to start your first pipeline run"

### New skill: `check-auth`

**Trigger:** "check auth", "re-authenticate", `/check-auth`, called from `onboarding`

**Behavior:**
- Read active providers from `config/user.yaml`
- For each active provider: `python3 scripts/providers/<provider>/check_auth.py <cdp_url>`
- Report per provider: ✅ authenticated / ❌ needs login
- For providers needing login: instruct user to log in in the Chrome window, then re-run `check-auth`
- Can be run at any time

### New skill: `run-scraping-pipeline`

**Trigger:** "run scraping", "scrape jobs", "run pipeline for greenhouse berlin", etc.

**Behavior:**
- Reads `config/user.yaml` for active providers, locations, search_terms
- Accepts overrides: specific provider, specific location, or "all"
- Default: all active providers × all configured locations
- Invokes for each combination:
  ```bash
  python3 scripts/scraping_pipeline.py \
    --provider <name> \
    --location <loc> \
    --titles "<comma-separated search_terms>"
  ```
- Reports: scraped / new after dedup / ingested / failures per run
- On `AuthError`: tells user to run `check-auth` first

**Examples:**
```
"run scraping"                → all providers × all locations
"run greenhouse berlin"       → greenhouse × berlin only
"run all scrapers for spain"  → all active providers × spain
```

### New skill: `add-job-by-url`

**Trigger:** User pastes a job posting URL in Hermes chat, Telegram, or dashboard URL field

**Deduplication approach:** Check `jobs.url` column first (unique-indexed in DB) before enrichment. Company and title are not yet known, so `dedup_key` cannot be used at this stage. After enrichment sets title and company, `dedup_key` is written to the row.

**Flow:**
1. Accept URL
2. Check `SELECT id FROM jobs WHERE url = ?` — if found: report "already tracked as job ID N" and stop
3. Build minimal `ShallowJob(provider="manual", url=url, title="", company="", dedup_key=url, ...)` and call `ingest_jobs` → get `job_id`
4. Call `enrich_job(job_id)` — Hermes browses URL, extracts title/description/apply_url/salary/date, updates DB row including `dedup_key = f"{company}::{title}"`
5. Call `sanity_check_job(job_id)` — check against CV
6. Report: job ID, title, company, verdict (pass/skip/error), link to dashboard

**Uses existing pipeline functions** from `scripts/pipeline/` — not a reimplementation.

### Skills kept and generalized

**`job-research`:**
- Remove all references to "Zall"
- Read `db_path` from `config/user.yaml` instead of hardcoded path

**`apply-job`:**
- Remove all references to "Zall"
- The skill (a SKILL.md file) instructs the AI agent to read `config/user.yaml` via a bash command at the start of execution:
  ```bash
  python3 -c "import yaml; d=yaml.safe_load(open('config/user.yaml')); print(d['user']['name'], d['user']['email'], d['cv_path'], d['user']['resume_pdf_path'], d['user']['linkedin_url'])"
  ```
  The agent captures this output and uses the values in all form-filling steps, replacing the previously hardcoded email/name/CV path.
- Replace hardcoded `cv_master_content.md` reads with `$(python3 -c "import yaml; print(yaml.safe_load(open('config/user.yaml'))['cv_path'])")`

---

## Implementation order

1. **A first** — config generalization (user.yaml, gitignore, API key cleanup, requirements.txt, `--titles` arg to scraping_pipeline, `check_auth.py` CLI entrypoints, skills archive)
2. **C second** — SOUL.md rewrite + 3 new skills + generalize job-research and apply-job
3. **B last** — README, after everything is working and verified

---

## What is NOT in scope

- Auth automation (logging in for the user) — manual login only; `check-auth` just verifies
- New job board integrations
- Applying automatically (no submit button logic)
- Multi-user support
- Adding new location presets (documented as a community contribution path)
