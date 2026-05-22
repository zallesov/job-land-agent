# Kanban-Based Mass Job Research

For researching 50+ jobs at once — the `delegate_task` batch pattern (max 3 concurrent)
is too slow. Use the Hermes Kanban dispatcher instead.

## When to use this vs delegate_task

| Approach | Best for | Concurrency |
|----------|----------|-------------|
| `delegate_task` batches of 3 | 1–30 jobs | 3 |
| Kanban dispatch with `--max 5` | 30–300+ jobs | Configurable |

## Step 1: Create kanban tasks in bulk

Use a Python script that reads all `status='new'` jobs from SQLite and calls
`hermes kanban create` for each. Key flags:

```bash
hermes kanban create \
  "research job <ID>: <title> — <company> [<provider>]" \
  --body "<instructions with job_id=N db=/path/to/jobs.db>" \
  --assignee interviewprep \
  --skill job-research \
  --max-runtime 30m \
  --json
```

**Critical:** `--title` is a POSITIONAL argument, not a flag. Using `--title "..."` fails.

**Skill loading:** Use `--skill job-research` so the worker auto-loads the research skill
without needing the orchestrator to specify it in the prompt.

**Per-task body must include** `job_id=N db=/path/to/jobs.db` so the worker (which has
no access to the parent agent's context) can find the right job row.

The bulk creation script template is at `../scripts/bulk_create_research_tasks.py`
(relative to the interviews project root: `tmp/bulk_create_research_tasks.py`).

## Step 2: Disable gateway auto-dispatch

The gateway's `kanban.dispatch_in_gateway: true` dispatches periodically but does
NOT respect any YAML `max_concurrency` key — it spawns ALL ready tasks at once.
To control concurrency, either:

**Option A (recommended):** Disable gateway dispatch and use manual dispatch:
```bash
hermes config set kanban.dispatch_in_gateway false
hermes kanban dispatch --max 5   # run manually or via cron
```

**Option B:** Keep gateway dispatch but accept that all ready tasks spawn immediately
(only safe for small task counts, < 10).

## Step 3: Dispatch with concurrency control

```bash
# Process 5 tasks at a time
hermes kanban dispatch --max 5

# For ongoing processing, use a cronjob that dispatches every 2 minutes:
hermes cron create "every 2m" \
  --name "kanban-dispatch-5" \
  --prompt "Run: hermes kanban dispatch --max 5"
```

The `--max N` flag caps how many workers the dispatcher spawns per pass.
Workers that finish free up slots; the next dispatch pass picks up new ready tasks.

## Step 4: Monitor progress

```bash
hermes kanban stats                    # ready/running/done counts
hermes kanban ls --status running      # active workers
hermes kanban tail <task_id>           # follow a specific task
```

## Pitfalls

### max_concurrency in YAML does NOT control dispatch

Adding `max_concurrency: 5` under the `kanban:` config section has no effect.
The dispatcher ignores it. The ONLY way to limit concurrency is `hermes kanban dispatch --max N`.

### Gateway dispatch spawns everything immediately

When `dispatch_in_gateway: true`, the gateway runs dispatch internally without
the `--max` flag, spawning every ready task simultaneously. For 150+ tasks,
this overwhelms the LLM provider with parallel API calls.

### Reclaim stuck workers

If workers are killed mid-flight (gateway stop), tasks stay in `running` status.
Reclaim them to reset to `ready`:
```bash
hermes kanban reclaim <task_id>
# Or bulk:
hermes kanban list --status running --json | python3 -c "
import sys, json, subprocess
for t in json.load(sys.stdin):
    subprocess.run(['hermes', 'kanban', 'reclaim', t['id']])
"
```

### Workers need the job-research skill loaded

Without `--skill job-research` on task creation, workers may not have the
research workflow available. Always include it.
