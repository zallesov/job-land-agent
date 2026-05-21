# InterviewPrep Profile — Skill Pruning Guide

Profile: `interviewprep`
Purpose: Land Zall more software engineering interviews — resume work, job
pipeline, GitHub, outreach, coding interview practice.

## Current State (2026-05-19)

**Applied configuration:** 90 skills disabled, 2 kept.
Chosen by user — caveman for compressed communication, macos-computer-use
for macOS desktop/browser control. All other builtins disabled.

Estimated savings: ~3,450 tokens/turn (92 → 2 skills).

## Keep (2 skills, as applied by user)

- caveman                (ultra-compressed communication mode)
- macos-computer-use     (macOS desktop drive — closest to browser/playwright)

## Remove (90 skills — all others)

Everything else. Notable categories fully disabled:
- All creative, mlops, media, research, gaming, apple, red-teaming
- All GitHub, productivity, development tools
- All workflow/kanban/mcp
- User's local skills (job-pipeline, terminal-games)

The user explicitly chose minimalism — only what's needed for browser
automation and efficient communication. Re-enable specific skills as
needed via the interactive `hermes --profile interviewprep skills config`
or by removing entries from `skills_disabled` in config.yaml.

## How to Apply

### Method 1: Non-interactive (config.yaml) — RECOMMENDED

Add `skills_disabled` at the **top level** of the profile's config.yaml
(NOT nested under `skills:`):

```yaml
skills_disabled:
  - skill-name-one
  - skill-name-two
```

Full example with all irrelevant skills disabled:

```yaml
skills_disabled:
  - airtable
  - apple-notes
  - apple-reminders
  - architecture-diagram
  - arxiv
  # ... (60+ skills, see actual config for full list)
  - yuanbao
```

Then `/reset` or start a new session. Verified working as of 2026-05-19.

**Pitfall:** Do NOT nest `disabled:` under `skills:`. The key is
`skills_disabled` at config top level (sibling of `skills:`, not child).

### Method 2: Interactive (requires real terminal)

```bash
hermes --profile interviewprep skills config
```

Toggle off each category above, then `/reset` or start a new session.
Changes take effect on next session — they do NOT apply mid-conversation
to preserve prompt caching.
