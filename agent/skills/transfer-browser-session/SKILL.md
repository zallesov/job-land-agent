---
name: transfer-browser-session
description: Use to carry an authenticated browser session (cookies + localStorage) from the local machine to a remote Hermes, so the remote Chrome can browse as the user. Manual, one session file.
---

# Transfer Browser Session (local → remote)

Moves a logged-in provider session to the remote Hermes (path B). The remote has Chrome +
CDP + Playwright + agent-browser installed (see `docker/hermes-agent/Dockerfile`) but no
login — this skill carries the session over as one file.

This is **manual and deliberate**: sessions are sensitive (they grant access as the user).
Do not automate it on a schedule or commit the session file.

## 1. Export on the local machine

Local Chrome must be logged in (see `wellfound-login`). Export the full browser state
(cookies + localStorage + sessionStorage):

```bash
agent-browser close --all
agent-browser --cdp 9222 state save session.json
```

`session.json` is Playwright storageState shape (`cookies` + `origins`). It contains the
provider session AND the bot-clearance cookies (`datadome`, `cf_clearance`) — treat it as
a secret.

## 2. Transfer to the remote (secure)

```bash
# encrypt, copy, decrypt on the other side (do not send plaintext)
openssl enc -aes-256-cbc -pbkdf2 -salt -in session.json -out session.json.enc -pass pass:<PASS>
scp session.json.enc <remote>:/opt/data/profiles/joblandagent/session.json.enc
# on remote:
openssl enc -d -aes-256-cbc -pbkdf2 -in session.json.enc -out session.json -pass pass:<PASS>
```

Place `session.json` under the profile root (`/opt/data/profiles/joblandagent/`).

## 3. Import on the remote

Start Chrome (Linux branch of `start-chrome.sh` runs it headed under Xvfb), then inject
the session into the live CDP browser:

```bash
bash start-chrome.sh
python3 scripts/load_session.py session.json --verify https://wellfound.com/jobs
```

`load_session.py` attaches over CDP (does not launch a browser), writes the cookies and
localStorage into the running context, and the `--verify` URL confirms auth (expect a
logged-in title, not a login/`restricted` page).

## Remote stealth requirements (or DataDome re-challenges)

The session cookies are tied to the original fingerprint. On the remote, match it:

- **User-Agent**: launch Chrome with `CHROME_UA="<the UA the session was created with>"`.
- **Proxy**: `CHROME_PROXY=<residential-ish proxy>` — bare datacenter IPs get scored hard.
- Headed-under-Xvfb (the Linux default here), NOT `--headless`.

If verify shows a login or DataDome block: the clearance expired or the fingerprint/IP
drifted — re-export a fresh session locally and/or switch proxy, then re-import.

## Notes

- Alternative to the session file: copy the whole `.chrome-profile` dir (also portable via
  `--use-mock-keychain`). The session file is lighter and provider-scopable; the profile
  is the most faithful but larger.
- After import, the normal provider flows (`wellfound-flow`, etc.) run unchanged on the
  remote — they just use the now-authenticated Chrome on CDP 9222.
- Delete `session.json` from both machines once imported.
