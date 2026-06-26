---
name: wellfound-check-auth
description: Use to verify there is a live authenticated Wellfound session on the local CDP browser before scraping. If logged out, directs the user to wellfound-login.
---

# Wellfound Check Auth

Confirms a usable Wellfound session before any parse/enrich step. Read-only.

## Workflow

1. Ensure the visible CDP browser is up:
   ```bash
   curl -s http://localhost:9222/json/version | grep -q '"Browser"' || echo NOT_RUNNING
   ```
   If `NOT_RUNNING`, the session cannot be checked — go to **wellfound-login** (it launches
   Chrome) and stop.

2. Verify the Wellfound session (drive the visible browser; see the `read-web-pages` skill
   for why `--cdp 9222` is mandatory):
   ```bash
   agent-browser close --all
   agent-browser --cdp 9222 open https://wellfound.com/jobs
   agent-browser --cdp 9222 snapshot -i | grep -iE "Avatar|restricted|Log in"
   ```

3. Interpret:
   - **Logged in** → an avatar / profile marker (e.g. `Avatar for <name>`). Report OK,
     the flow may continue to parse.
   - **Logged out** → a `Log in` form. Tell the user to run **wellfound-login** and stop.
   - **`Access temporarily restricted` / DataDome iframe** → bot block, NOT a logout.
     Usually the headless bundled browser was used (missing `--cdp 9222`) or the IP got
     rate-scored. Fix the connection / slow down; do not treat as logged out.

## Hard rule

Judge auth by the **rendered page**, not by reading cookie files or storage. Do not type
the user's password — login is manual in the visible window (wellfound-login).
