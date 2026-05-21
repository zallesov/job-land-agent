# Pipeline Architecture Review — May 18, 2026

## Context

Claude implemented Plans 1–7 of the master pipeline. The implementation produces working ingestion, tagging, research, Telegram notifications, and a Next.js dashboard. DB has 68 jobs from 17 companies across 2 pipeline runs.

## Gap: Hermes Isn't Supervising

The plans describe Hermes as orchestrator, but the implementation uses Hermes only as a `hermes send` transport. Everything else is manual Python scripts:

| Function | Plan says | Reality |
|----------|-----------|---------|
| Daily scraping | Hermes cron triggers scrapers | Manual Playwright browser script |
| Scraper monitoring | Hermes tracks exit codes | None — run manually, check visually |
| Ingestion | Hermes triggers after scrape | Manual `python ingest_provider_outputs.py` |
| Research | Hermes delegates to agent | `research_job.py` calls Anthropic API directly |
| Notification | Hermes sends digest | Works, but only if script is called manually |

## Research: Direct API vs. Agent Delegation

Current `research_job.py`:
```python
client = anthropic.Anthropic()
message = client.messages.create(model="claude-sonnet-4-6", ...)
```
This is a single LLM call — Claude generates company facts from training data with zero live research. No browser, no web_search, no source verification. The LLM might hallucinate Glassdoor ratings, funding rounds, or employee counts.

Target: Hermes calls InterviewPrep agent, which uses:
- `browser_navigate` → company website (legitimacy, careers page)
- `web_search` → LinkedIn (size, trends), Crunchbase (funding), Glassdoor (reviews), news (risk signals)
- Cross-reference with Zall's profile from agent memory

## Two Hermes Workflows Needed

### Workflow A: Daily Scraping Pipeline
```
Hermes cron (morning Europe/Madrid)
  → Spawn scraper (headless subprocess, not interactive browser)
  → Capture exit code + stdout/stderr
  → On success: run ingest_provider_outputs.py
  → On failure: log to pipeline_runs, Telegram alert, continue
  → Run tag_new_jobs.py
  → Send Telegram daily digest
```

### Workflow B: Research Job (dashboard-triggered)
```
Dashboard "Research" button click
  → Next.js API inserts agent_commands row (status=pending)
  → Next.js spawns: hermes delegate interviewprep-research --command-id N
  → Agent loads job context from SQLite
  → Agent does live research (browser + web_search)
  → Agent writes company_research + job_assessments to SQLite
  → Agent returns summary
  → Hermes sends Telegram notification
  → Hermes updates agent_commands.status
```

## Scraper State

Greenhouse scraper (`scrape_greenhouse_playwright_mcp.test.js`):
- 230 lines of Playwright browser automation
- Searches 3 queries × 2 locations = 6 permutations against my.greenhouse.io/jobs
- Follows each job link to scrape description details
- Outputs normalized JSON array at `outputs/greenhouse/runs/greenhouse_jobs_live_YYYY-MM-DD.json`
- Produced 68 jobs (all currently in DB)
- **Blocker**: Requires interactive browser session. Needs headless mode + CLI wrapper for Hermes to spawn.

## DB State (after 2 pipeline runs)
- 68 jobs, 17 companies, 86 events
- Tables: jobs, companies, company_research, job_assessments, applications, agent_commands, pipeline_runs, events
- Schema enforced via db.py helpers, not raw SQL elsewhere
