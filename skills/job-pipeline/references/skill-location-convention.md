# Skill Location Convention

## Where skills live

| Directory | Owner | Registered in |
|---|---|---|
| `/Users/zall/interviews/skills/` | Job pipeline skills (from legacy `.codex/skills/`) | Hermes via `skills.external_dirs` in config.yaml |
| `~/.hermes/profiles/interviewprep/skills/` | Hermes-native skills (built-in, manually created) | Auto-discovered by profile |

## The external_dirs pattern

Hermes can resolve skills from external directories. This was configured May 19, 2026 when the `.codex/skills/` folder was migrated to `/Users/zall/interviews/skills/`.

### Config (config.yaml)

```yaml
skills:
  external_dirs:
  - /Users/zall/interviews/skills
```

### How Hermes loads skills

```
interviewprep --skills job-research -z "..."
```

Hermes scans:
1. Its own skills directory (`~/.hermes/profiles/interviewprep/skills/`)
2. All directories listed in `skills.external_dirs`

First match wins. If a skill is found in both, the one from external_dirs is used.

### Verification

```bash
# Check the skill is findable
ls /Users/zall/interviews/skills/<SKILL_NAME>/SKILL.md

# Check the config is correct
grep -A2 external_dirs ~/.hermes/profiles/interviewprep/config.yaml

# Test resolution (silent — just confirms no errors)
interviewprep --skills job-research -z "ping" --dry-run 2>&1 | head -5
```

### What happens when a skill is missing

Hermes starts with **zero tools**. The agent receives the prompt as a bare chat query, answers with prose, and exits. The `agent_commands` row stays `pending` forever.

**Signs of a missing skill:**
- The spawned process's log file contains prose describing the job rather than executing research
- No DB writes (agent_commands.status unchanged)
- Exit with no visible error

## Migration history

**May 19, 2026:** Removed `/Users/zall/interviews/.codex/` (moved to `./.codex.bak/`). Copied all 10 skills from `.codex/skills/` to `/Users/zall/interviews/skills/`. Set `external_dirs` in config.yaml. Skills now available to both Hermes (via the dashboard's `interviewprep --skills NAME` spawn) and Codex (via `codex exec`).

## Affected skills (migrated from .codex)

- `apply-job`
- `assess-jobs-due-diligence`
- `consolidate-jobs-workbook`
- `daily-pipeline`
- `greenhouse-daily-export`
- `greenhouse-scraper`
- `job-research`
- `job-scraping-pipeline`
- `jobleads-daily-export`
- `jobleads-scraper`
- `scrape-and-research-job`
