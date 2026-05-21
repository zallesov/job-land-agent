---
name: check-auth
description: Verify browser sessions for all active job board providers. Runs check_auth.py for each active provider and reports pass/fail. Triggered by "check auth", "re-authenticate", "/check-auth", or called from onboarding.
---

# Check Auth

## Trigger

Run when: "check auth", "re-authenticate", "check my sessions", `/check-auth`, or invoked from the onboarding skill.

## Execution Rules

- Run for every provider where `providers.<name>: true` in `config/user.yaml`.
- Report per provider: ✅ authenticated / ❌ needs login.
- For providers needing login: give exact instructions for the user to log in via the Chrome window, then suggest re-running this skill.
- Can be run at any time — safe to run repeatedly.

## Step 1: Read active providers

```bash
python3 -c "
import yaml
d = yaml.safe_load(open('config/user.yaml'))
active = [p for p, enabled in d['providers'].items() if enabled]
print(' '.join(active))
"
```

## Step 2: Run check_auth for each active provider

For each active provider name:

```bash
python3 scripts/providers/<provider>/check_auth.py http://localhost:9222
```

Capture exit code and any output. `AuthError` in output means ❌. Clean exit means ✅.

## Step 3: Report results

Print a summary like:

```
Auth check results:
  greenhouse  ✅ authenticated
  jobleads    ❌ needs login
  wellfound   ✅ authenticated
```

## Step 4: For each failed provider

Tell the user:

> Open the Chrome window (run `~/start-chrome.sh` if not running), navigate to <provider login URL>, log in manually, then run `/check-auth` again to verify.

Provider login URLs:
- **Greenhouse:** https://my.greenhouse.io/users/sign_in
- **JobLeads:** https://www.jobleads.com/login
- **Wellfound:** https://wellfound.com/login
- **Sprout:** https://app.usesprout.com/login

## Chrome Pre-Flight

Before running any check_auth:

```bash
curl -s http://localhost:9222/json/version | python3 -c "import sys,json; d=json.load(sys.stdin); print('Chrome OK:', d.get('Browser','unknown'))" 2>/dev/null || echo "NOT_RUNNING"
```

If `NOT_RUNNING`: tell user to run `~/start-chrome.sh` first.
