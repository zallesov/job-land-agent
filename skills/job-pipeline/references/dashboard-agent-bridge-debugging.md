# Dashboard → Agent Bridge: Orphaned Command Debugging

## How the dashboard spawns research/apply

The dashboard's `/api/commands/route.ts` has a `COMMAND_CONFIG` that maps command types to Hermes skill names:

```typescript
const COMMAND_CONFIG = {
  research_job: {
    skill: 'job-research',
    prompt_template: (job: Job) => `Research job_id=${job.id} ...`,
  },
  apply_job: {
    skill: 'apply-job',
    prompt_template: (job: Job) => `Apply to job_id=${job.id} ...`,
  },
};
```

On button click, it:
1. INSERTs an `agent_commands` row with `status='pending'`
2. Spawns: `interviewprep --yolo --skills <skill_name> -z "<prompt>"`
3. Does NOT wait for or track the spawned process

## The skill gap (root cause of most orphaned commands)

Historically, neither `job-research` nor `apply-job` existed in the Hermes skill library. When Hermes started, it would load zero tools, get the prompt as a bare chat query, write a prose response to the log, and exit — leaving the `agent_commands` row stuck at `pending`.

**Fixed May 19, 2026:** Both skills now live at `/Users/zall/interviews/skills/job-research/` and `/Users/zall/interviews/skills/apply-job/`. Hermes resolves them via:

```yaml
# in ~/.hermes/profiles/interviewprep/config.yaml
skills:
  external_dirs:
  - /Users/zall/interviews/skills
```

The `.codex/` directory was removed. All former Codex skills moved to `/Users/zall/interviews/skills/`.

**If orphaned commands still appear**, check:

```bash
ls /Users/zall/interviews/skills/<SKILL_NAME>/SKILL.md         # does the file exist?
grep external_dirs ~/.hermes/profiles/interviewprep/config.yaml # is it registered?
```

## The auth gap (second failure mode)

Commands 6, 8, 13 DID run `research_job.py` (started_at + finished_at set) but failed because:

```
Could not resolve authentication method. Expected one of api_key, auth_token...
```

The script uses `anthropic.Anthropic()` which reads `ANTHROPIC_API_KEY` from the environment. On Zall's machine, this variable is not set.

## Triaging a stuck command

### Step 1: Find pending commands

```sql
SELECT ac.id, ac.payload_json, ac.created_at, j.title, j.url
FROM agent_commands ac
LEFT JOIN jobs j ON json_extract(ac.payload_json, '$.job_id') = j.id
WHERE ac.command_type = 'research_job' AND ac.status = 'pending'
ORDER BY ac.created_at;
```

### Step 2: Read the log

```bash
cat /Users/zall/interviews/outputs/research-logs/job_<JOB_ID>_cmd_<CMD_ID>.log
```

### Step 3: Map log to root cause

| Log says... | Problem | Fix |
|---|---|---|
| "Here's what I found: Job #N ..." (prose answer, describes the job) | **Missing skill** — Hermes couldn't load the requested skill via external_dirs | Fix config.yaml or run `research_job.py` directly |
| `file not found` or empty log | **Hermes crash** — binary or flags broken | Check `~/.local/bin/interviewprep`, check `$PATH` |
| "Could not resolve authentication method" | **Auth gap** — no ANTHROPIC_API_KEY | Set key or swap to local LM Studio |

### Step 4: Recovery

For missing skill cases (most common):

```bash
cd /Users/zall/interviews
python3 scripts/research_job.py --db jobs.db --job-id <JOB_ID> --command-id <CMD_ID>
```

The `--command-id` flag is what makes the script update the `agent_commands` row from `pending` to `succeeded` or `failed`.

## Relevant DB queries

```sql
-- Check if a command ran (has started_at)
SELECT id, status, started_at, finished_at, error FROM agent_commands WHERE id = <CMD_ID>;

-- Check which jobs have assessments but status stuck at 'new'
SELECT j.id, j.title, j.status FROM jobs j
JOIN job_assessments ja ON ja.job_id = j.id
WHERE j.status = 'new' AND ja.assessment_status = 'researched';

-- Fix: set job status to match assessment
UPDATE jobs SET status = 'researched', updated_at = datetime('now') WHERE id = <JOB_ID>;
```
