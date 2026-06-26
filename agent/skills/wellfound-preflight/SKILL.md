---
name: wellfound-preflight
description: Use first in the Wellfound flow to fail fast — checks Chrome/CDP, headed (not headless), required scripts, tmp writable, salary floor, and reminds to verify session + JobLandMCP write tools.
---

# Wellfound Preflight

Run before any real Wellfound work so failures happen before effort is spent.

## Run

```bash
python3 scripts/wellfound_preflight.py
```

Checks (exit 1 if any fail):
- Chrome CDP reachable on `localhost:9222`
- browser is **headed** (UA is not `HeadlessChrome`)
- required scripts/files exist at the profile root
- `tmp/wellfound/` is writable
- `desired_salary` set in `config/user.yaml`

Scripts are self-locating (paths resolve from the script location), so this works whether
the cwd is the profile root (`scripts/...`) or the monorepo checkout (`agent/scripts/...`).

## Two checks the script cannot do (agent-side)

1. **Wellfound session live** — run **wellfound-check-auth** (open `/jobs`, look for the
   avatar, not a login/`restricted` page).
2. **JobLandMCP write tools available** — confirm `jobs_find_by_url`, `jobs_create`,
   `jobs_update` are in the MCP tool list. If missing, stop — the flow cannot persist.

If Chrome is down: `bash start-chrome.sh` (local) — see **wellfound-login** to log in.
