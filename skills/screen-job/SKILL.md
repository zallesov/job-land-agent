---
name: screen-job
description: Screen a job against the candidate's CV and produce a lightweight assessment verdict.
---

# screen-job

Screen a job against the candidate's profile and produce a lightweight assessment.

## Batch screening (preferred for multiple jobs)

```bash
python3 scripts/batch_screen_jobs.py --job-ids 42,43,44
python3 scripts/batch_screen_jobs.py --job-ids 42 43 44 --workers 5
```

**If `batch_screen_jobs.py` is missing** (it can get deleted during project cleanup), call the module directly:

```bash
python3 -c "
import sys; sys.path.insert(0, 'scripts')
from pipeline.screen_jobs_batch import screen_jobs_batch
import os
# DEEPSEEK_API_KEY must be set first
ok_ids, failures = screen_jobs_batch([42, 43, 44], max_workers=5)
print(f'{len(ok_ids)} ok, {len(failures)} failed')
"
```

Runs up to 5 parallel DeepSeek API calls directly — no Hermes agent overhead. Prefer this over calling `screen-job` in a loop.

## Single job via Hermes

`Use skill screen-job. job_id: 42. cv_path: /path/to/cv.md`

## Prerequisites

**1. DEEPSEEK_API_KEY must be set in the environment.** The batch screening script calls the DeepSeek API directly. The key lives in `hermes-profile/.env`. Export it before running:

```bash
export DEEPSEEK_API_KEY=$(python3 -c "
with open('hermes-profile/.env') as f:
    for line in f:
        if line.startswith('DEEPSEEK_API_KEY='):
            print(line.split('=', 1)[1].strip())
")
```

**2. The job must have a description.** Screening reads the `description` field from the DB. If `description` is NULL or too short (<50 chars), the verdict will be `"Need Research"` — essentially a waste of a call.

Check before batch-screening existing jobs:
```sql
SELECT id, title, posted_company_name FROM jobs
WHERE provider='<name>' AND (description IS NULL OR length(description) <= 50);
```

If many are missing descriptions, re-enrich first (see `enrich-job` skill's batch workflow).

## Known failures

### "parse error: substring not found"

The DeepSeek API returned a response that the batch script couldn't parse as valid JSON. This is a transient DeepSeek issue — the model occasionally outputs non-JSON text alongside the JSON block.

**Fix:** Re-run the failed job IDs. If the same jobs fail consistently, screen them via the Hermes single-job workflow instead (see "Single job via Hermes" above). The Hermes agent's structured output extraction handles malformed responses better than the batch script's parser.

### All jobs fail with "DEEPSEEK_API_KEY not set"

The key was not exported to the environment. See Prerequisites §1 for the export command.

## Task

1. Read the CV from cv_path
2. Read `config/user.yaml` — extract `job_preferences`, `languages`, and `desired_salary` (may be empty strings)
3. Read the job from the database using job_id (use your DB read tools). Fields: title, description, company name, location, remote_scope, salary_range.
4. Assess the job against the candidate's profile. Evaluate ALL of the following:
   - **apply_verdict**: one of "Strong Apply" | "Apply with Caution" | "Need Research" | "Skip"
     - "Strong Apply": clear match — right seniority, tech stack, remote, no red flags, aligns with user preferences
     - "Apply with Caution": worth applying but notable caveats (borderline tech fit, unclear remote, no salary info)
     - "Need Research": potentially interesting but cannot assess without more context (no description, vague company, unclear remote policy)
     - "Skip": hard disqualifiers — on-site only, junior/entry-level, completely unrelated domain, requires relocation outside target list (Berlin, Spain, EU remote), OR explicitly conflicts with `job_preferences` (e.g. fintech role when user said "no fintech"), OR requires a language the user doesn't speak per `languages`
   - **relevance_score**: 0–100 based on tech stack fit, seniority match, remote eligibility, domain relevance
   - **one_line_summary**: one sentence describing the role and fit
   - **seniority_fit**: brief note on level match
   - **tech_stack_fit**: brief note on tech overlap with candidate's profile
   - **remote_eligibility**: what the job says about remote; candidate target is EU remote / Berlin / Spain
   - **salary_assessment**: posted salary vs `desired_salary`; flag if clearly below target or "Not disclosed"

## Output

Respond with a single JSON block. No prose.

```json
{
  "status": "success",
  "apply_verdict": "Strong Apply",
  "relevance_score": 85,
  "one_line_summary": "Senior backend Python role, fully remote EU, great stack fit",
  "seniority_fit": "Senior IC, matches target level",
  "tech_stack_fit": "Python, Postgres, Kafka — strong overlap",
  "remote_eligibility": "Fully remote, EU timezone",
  "salary_assessment": "€90k–120k posted"
}
```

Failure (cannot read job or CV):
```json
{"status": "failure", "error": "could not load job description"}
```

## Rules
- apply_verdict is always one of the four exact strings above
- relevance_score must be an integer 0–100
- Do NOT research the company — assess only from the job description and CV
- If description is missing or too short to assess, use verdict "Need Research"
- `job_preferences` and `languages` are hard constraints for "Skip" — if the job clearly violates them, verdict is "Skip" regardless of tech fit
- `desired_salary`: if posted salary is clearly below the target range, downgrade verdict to "Skip" or "Apply with Caution" depending on severity
- If `job_preferences`, `languages`, or `desired_salary` are empty strings, ignore them
