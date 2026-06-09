# Heuristic Fallback Screen

## When does this happen

`screen_job()` has three paths:

1. **Hermes agent call** (line 183) — only if `hermes_call` is set. Currently `None` in the standalone `screen_job.py` module. Dead code.
2. **DeepSeek API call** (line 224) — requires `DEEPSEEK_API_KEY` loaded from `.env`. This is the path we want.
3. **Local heuristic** `_local_assessment()` (line 97) — keyword-based fallback. **This path is silent — no error, no warning.**

The script reaches path 3 when:
- No `DEEPSEEK_API_KEY` in environment → path 2 skipped, path 3 runs
- DeepSeek API call fails (timeout, HTTP error, parse error) → catches the exception and runs path 3
- DeepSeek returns unparseable JSON → catches parse exception and runs path 3

## How to detect it

Check the job_assessments row. If `seniority_fit`, `tech_stack_fit`, `salary_assessment`, or `remote_eligibility` contain `"Heuristic fallback"`, the real screening did not run.

## Why it produces bad verdicts

`_local_assessment()` is a simple keyword scan that checks text in this order:

1. `"sales"`, `"marketing"`, `"account executive"`, `"customer success"` → **Skip, R:5, "Non-engineering role."**
2. `"health"`, `"healthcare"`, `"medical"`, `"clinical"`, etc. → **Skip, R:10, "Health-domain role outside the target profile."**
3. `"security engineer"`, `"infosec"` → **Skip, R:10, "Security-focused role..."**
4. `"engineer"`, `"developer"`, `"platform"` → **Strong Apply, R:85** (only if no earlier match)

Because it checks marketing BEFORE engineer, a Senior AI Engineer at an ad-tech company gets "Non-engineering role" — even though the role is building LLM-powered products. Same for healthcare — a Staff Software Engineer building AI agents at a health startup gets "Health-domain role outside the target profile."

## How to fix it

If you detect heuristic fallback in an assessment:

**Option A: Ensure DEEPSEEK_API_KEY is loaded and re-screen.**

Check the `.env` path first. The script loads `.env` from `$PROJECT_ROOT/.env` → `$HERMES_HOME/.env`:

```bash
ls -la $HERMES_HOME/.env  # should exist and have DEEPSEEK_API_KEY
```

Then re-screen via the module directly:

```bash
cd /Users/zall/interviews
python3 -c "
import os
# Load .env manually to verify
hp = os.environ.get('HERMES_HOME', '')
if hp and os.path.exists(f'{hp}/.env'):
    for line in open(f'{hp}/.env'):
        line = line.strip()
        if '=' in line and not line.startswith('#'):
            k, _, v = line.partition('=')
            os.environ.setdefault(k.strip(), v.strip())

from scripts.pipeline.screen_job import screen_job
r = screen_job(<job_id>)
print(r.data.get('apply_verdict'), r.data.get('relevance_score'))
"
```

**Option B: Skip screening and go straight to research.**

If you can't fix the .env issue, research the job properly (via `db_write_research.py`) which produces authoritative scores and overwrites the bad assessment. Research also sets `jobs.research_status='researched'` which prevents the screening from being re-triggered.
