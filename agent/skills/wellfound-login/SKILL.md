---
name: wellfound-login
description: LOCAL ONLY. Use to create a Wellfound session by launching the visible CDP Chrome and letting the user log in manually. Cannot run on a remote/headless host.
---

# Wellfound Login (local only)

Creates/refreshes the Wellfound session in the persistent local Chrome profile. **Local
machine only** — it needs a visible browser window for the user to log in and solve any
bot challenge. Do not attempt on a headless server.

## Why manual

Wellfound login is behind DataDome + (Google) OAuth. A controlled/headless browser is
blocked. The reliable path is a real visible Chrome the user logs into by hand once; the
session then persists in the profile and survives restarts and IP changes.

## Workflow

1. Launch the visible stealth Chrome (CDP 9222, profile `.chrome-profile`):
   ```bash
   bash start-chrome.sh
   curl -s http://localhost:9222/json/version | grep '"Browser"'   # expect Chrome/<v>, not Headless
   ```

2. Open the login page in that window:
   ```bash
   agent-browser close --all
   agent-browser --cdp 9222 open https://wellfound.com/login
   ```

3. **Tell the user to log in manually** in the visible window (email/password or
   "Log in with Google", including any 2FA / CAPTCHA). Do not type their password.

4. Wait for the user to confirm, then verify with **wellfound-check-auth**.

## Notes

- The profile (`.chrome-profile`, `--use-mock-keychain`) keeps cookies portable and
  persistent. One manual login lasts across restarts until the session expires.
- For moving this session to a server, see the "Session portability" section of the
  `read-web-pages` skill (copy the profile dir or export `state save` JSON; match UA +
  use a residential-ish IP).
