---
name: check-auth
description: Use when verifying or restoring visible-browser authentication for JobLand providers.
---

# Check Auth

## Hard Rule

Verify auth by **navigating the visible browser** and reading the rendered page, or via
a JobLandMCP provider-auth check. Do not parse raw cookie databases, profile files, or
backend records to judge auth state. (Exporting a full session with
`agent-browser state save` for transfer is fine — that is not an auth check.)

## Workflow

1. If a JobLandMCP provider-auth check tool exists, call it for the requested provider.
2. Otherwise, make sure visible Chrome is running (`bash agent/start-chrome.sh`; see
   `read-web-pages` skill for the launch + CDP details), then open the provider's
   authenticated page in it and read the rendered state.
3. If logged out, open the provider login page and let the user enter credentials
   manually in the visible window. Never type their password yourself.
4. Confirm by checking visible page state for a logged-in marker.

## Verify via agent-browser

```bash
agent-browser close --all
agent-browser --cdp 9222 open https://wellfound.com/jobs
agent-browser --cdp 9222 snapshot -i | grep -iE "Avatar|<your name>|restricted|Log in"
```

- Logged in → a user/avatar marker (e.g. `Avatar for <name>`), profile/nav links.
- Logged out → a "Log in" form.
- `Access temporarily restricted` / a DataDome iframe → bot block, not a logout. This
  usually means the headless bundled browser was used (missing `--cdp 9222`) or the IP
  got rate-scored. Fix the connection / slow down; do not treat it as logged out.

## Provider Login URLs

- Greenhouse: `https://my.greenhouse.io/users/sign_in`
- JobLeads: `https://www.jobleads.com/login`
- Wellfound: `https://wellfound.com/login`
- Sprout: `https://app.usesprout.com/login`

Do not read cookies, local profile files, browser storage files, or backend records to
infer auth — navigate and look at the page instead.
