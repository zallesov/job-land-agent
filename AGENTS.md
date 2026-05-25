# JobLandAgent — Project Context

## Key Paths

| Resource | Path |
|---|---|
| User config | `config/user.yaml` |
| CV | `config/cv.md` |
| Database | `jobs.db` (override via `db_path` in config) |
| Skills | `skills/` |
| Pipeline scripts | `scripts/` |
| Providers | `scripts/providers/<name>/` |

## Chrome CDP

All scraping and enrichment requires Chrome running at `http://localhost:9222`.

Pre-flight check:
```bash
curl -s http://localhost:9222/json/version | grep -q "{" && echo "OK" || echo "NOT_RUNNING"
```

If `NOT_RUNNING`: tell user to run `bash start-chrome.sh`. Do not proceed.

### ALL CHROME OPERATIONS MUST BE VISIBLE

**The user watches the Chrome window.** Every page opened via CDP (`ctx.new_page()`, `page.goto()`) MUST call `page.bring_to_front()` immediately so the tab becomes visible and focused in the Chrome window. No invisible/background page creation.

Rules:
- After `page = ctx.new_page()`, call `page.bring_to_front()` before any navigation.
- Do NOT use `Target.createTarget` with background flags or `createPage` in hidden mode.
- `page.close()` at the end is fine — the tab will disappear, but the user saw the work happen.
- Exception: only skip `bring_to_front` if the user explicitly asks for quiet/no-visual mode.

## Pipeline Scripts

| Script | Purpose |
|---|---|
| `python3 scripts/scraping_pipeline.py --provider <name>` | Scrape one provider end-to-end |
| `python3 scripts/add_job_by_url.py --url <url>` | Add a single job by URL |
| `python3 scripts/enrich_job.py --job-id <id>` | Enrich one job via CDP |
| `python3 scripts/enrich_jobs_batch.py --job-ids <ids>` | Enrich multiple jobs |

Providers: `greenhouse` | `jobleads` | `wellfound` | `sprout` | `hirify`

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
| `apply-job` | User says "apply to job N" |
| `run-dashboard` | Start dashboard and open in browser |

## Job Status Lifecycle

```
new → screened → researched → applied
    → enrich_failed
    → skip
```

| Status | Meaning |
|---|---|
| `new` | Ingested (and enriched if pipeline ran); not yet screened |
| `screened` | screen-job completed, assessment in `job_assessments` |
| `enrich_failed` | CDP enrichment failed — no description |
| `skip` | Filtered out (duplicate key, irrelevant) |
| `researched` | Full research done |
| `applied` | Application submitted |

## Database

SQLite at `jobs.db`. Key tables: `jobs`, `job_assessments`.

```sql
-- Jobs needing enrichment
SELECT id, url FROM jobs WHERE status = 'enrich_failed';

-- Jobs needing screening
SELECT id FROM jobs WHERE status = 'new' AND length(description) > 50;

-- Screened jobs with assessments
SELECT j.id, j.title, j.posted_company_name, a.apply_verdict, a.relevance_score
FROM jobs j JOIN job_assessments a ON a.job_id = j.id
ORDER BY a.relevance_score DESC;
```

## Codebase Rules

- Scripts live in `scripts/`. Never create standalone scripts elsewhere.
- Provider scrapers: `scripts/providers/<name>/scrape_jobs.py`
- Skills live in `skills/`. Never create skills in `hermes-profile/skills/`.
- All providers run via `scripts/scraping_pipeline.py` — never call scrape scripts directly.
- Scrapers return all jobs as `status="new"` — no filtering at scrape time.

## Temporary Files

Use `tmp/` for any temporary or one-off files: `.py`, `.sh`, `.sql`, `.json`, scratch scripts, data dumps. Never litter the project root or `scripts/` with throwaway files.

## Modifying Skills and Scripts

**Do not modify files in `skills/` or `scripts/` unless explicitly asked.**

If a task requires a change to a skill or script, stop and ask the user before making it. Explain what change is needed and why. Wait for approval.

For one-off operations that would normally require a script change, write a throwaway script in `tmp/` instead.
