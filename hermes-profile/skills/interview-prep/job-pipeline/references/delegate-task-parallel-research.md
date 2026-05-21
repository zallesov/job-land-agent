# Parallel Research via delegate_task

When the `research_job.py` pipeline script is blocked (missing API key, env issue, script bug), use `delegate_task` with parallel tasks as the workaround. This approach is faster than sequential research and avoids the blocked script entirely.

## When to Use

- `research_job.py` fails silently (exit code 1, no error output)
- Multiple jobs need researching at once (up to 3 concurrent tasks)
- You want live browser + web_search research rather than a single LLM call with stale data

## The Pattern

```python
# Pass all 3 job research tasks as a batch:
tasks = [
    {
        "goal": "Research Job 52 (Lineate): Read full description from Greenhouse, research company (services/dev shop), assess fit...",
        "context": f"Job: title='{j52_title}', url='{j52_url}', description='{j52_desc}', company='Lineate'...",
        "toolsets": ["web", "browser"]
    },
    {
        "goal": "Research Job 53 (Pairwise): ...",
        "context": "...",
        "toolsets": ["web", "browser"]
    },
    {
        "goal": "Research Job 58 (FeverUp): ...",
        "context": "...",
        "toolsets": ["web", "browser"]
    }
]

results = delegate_task(tasks=tasks)
# Each result: {goal, summary, success, ...}
```

## Key Settings

- `toolsets: ["web", "browser"]` — gives each subagent the research tools it needs
- `context` — must include job title, URL, company name, full description directly (subagents have NO memory of the parent conversation)
- Max 3 concurrent tasks (configured limit for this user)
- Each subagent is a leaf — cannot delegate further

## What Each Subagent Should Do

1. **Read the job posting** via browser_navigate → extract full description
2. **Research the company** — website, LinkedIn, Crunchbase, Glassdoor, news, funding
3. **Assess fit** against Zall's profile: tech stack, seniority level, remote eligibility, compensation, AI-native work, red flags
4. **Return structured result** — verdict, scores, one-line summary, assessment notes

## Post-Research: DB Write (Phase 2, status = 'researched')

After the delegate_task returns, the **parent agent** must write results to SQLite.
**This is ONLY triggered when the user explicitly says "research this job".**

1. Ensure company exists in `companies` table (INSERT OR IGNORE by normalized_name)
2. Fix company_id on the job record if it was wrong
3. Insert `company_research` row
4. Insert `job_assessments` row
5. Update `jobs.status = 'researched'` — ONLY on explicit user instruction
6. Mark `agent_commands` row as `succeeded` (with `finished_at` and `result_json`)

**Hard rule**: DB write is mandatory before reporting to the user. The report is a summary of what was saved, not a substitute.

## Why Not Fix the Script Instead?

- The env issue (ANTHROPIC_API_KEY not exported to child processes) is a Hermes session-level config problem
- Fixing it would require adding the key to `.zshrc`/`.bash_profile` or using Hermes config's `env` section
- The delegate_task workaround is faster for immediate research needs — fix the script as a separate task when there's downtime

## Pitfalls

- **Subagent summaries are self-reports**: A subagent that says "inserted to DB" may be wrong. Always verify by querying the DB after delegate_task returns.
- **Company name mismatch**: Subagents report company names inconsistently (e.g., "Pairwise" vs "Pairwise via Delart"). Normalize before DB insertion.
- **Bad company_id mappings**: New jobs from unknown scrapers may inherit the last-used company_id. Always check `jobs.company_id` points to the right company row.
- **Description extraction fails**: Some job boards (FeverUp, some Greenhouse instances) redirect to application forms without showing the description text in the DOM. In that case, estimate from the title and company profile, and note it in the assessment.
- **No context inheritance**: Each subagent starts cold. Put ALL relevant information (job title, URL, description body, company name) directly in `context` — don't make them look it up from scratch.
- **Browser runs in cloud, not locally**: When using `["browser"]` toolsets, the subagent's browser runs on Browserbase's infrastructure, not your local Chrome. No window pops up. This is correct behavior. The subagent can still navigate, click, type, scroll, and run JS. See `references/hermes-browser-infrastructure.md` in the job-pipeline skill for details.
- **No visual feedback by default**: If you or the user want to see what the browser is rendering, instruct the subagent to call `browser_vision()` and include the screenshot path (as `MEDIA:<path>`) in its summary. But use sparingly — each `browser_vision()` call consumes tool budget.
