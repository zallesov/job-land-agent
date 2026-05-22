# Chrome Setup: Dedicated Profile

## Architecture

The `start-chrome.sh` script (project root) launches Chrome with:

```
--remote-debugging-port=9222
--user-data-dir=<PROJECT_ROOT>/.chrome-profile
--restore-last-session
--use-mock-keychain
```

This creates a **dedicated Chrome profile** at `./chrome-profile/` (inside the project directory), completely separate from the user's everyday Chrome profile.

## Why `--use-mock-keychain`?

Chrome on macOS encrypts cookies via the system Keychain. When launched from a script (no GUI session context), a dialog pops up: *"keychain cannot be found to store Chrome"* — blocking startup and preventing CDP from binding. `--use-mock-keychain` bypasses this entirely, enabling headless/silent startup.

**Trade-off:** Chrome's built-in password manager won't save new passwords. But session cookies (login tokens) are stored in the SQLite `Cookies` database on disk and persist fine — that's all we need for job board auth.

## What This Means for Sessions

- **Logins persist within this profile only.** If you log into Greenhouse, Wellfound, JobLeads, etc. via the automation Chrome window, those cookies and sessions are saved in `.chrome-profile/Default/Cookies` and `Login Data`.
- **Your regular Chrome sessions do NOT carry over.** The automation profile starts empty. This is intentional — it isolates job board logins from your personal browsing.
- **Session restore requires normal close.** Sessions survive only if Chrome is closed normally (Cmd+Q or menu → Quit). A `pkill` or force-quit triggers clean exit, which DELETES `Current Session` and `Last Session` files — after that, even `--restore-last-session` has nothing to restore.

## How to Start

```bash
cd <project-root>
bash start-chrome.sh
```

## How to Stop

Close Chrome normally (Cmd+Q or menu → Quit Chrome). Do NOT use `pkill`.

## Critical: `--restore-last-session` Flag

Added May 22, 2026. Without this flag, Chrome's default startup behavior is "Open the New Tab page" (not "Continue where you left off"), meaning it never reads the stored session files. With the flag, tabs and login sessions are restored on next launch.

**Limitation:** This only works if Chrome exited normally. On `pkill` or crash, the `Current Session` and `Last Session` files are gone, and the flag has nothing to restore.

## Session Persistence Rules (hard-won knowledge)

| Action | Session on next start |
|---|---|
| Normal close (Cmd+Q, menu) | ✅ Restored via --restore-last-session |
| `pkill -f "Google Chrome"` | ❌ Clean exit → session files deleted |
| Force Quit (macOS) | ❌ Same as pkill |
| Crash | ❌ Clean exit handler may fire |

**After any session loss:** the user must re-login to all job board services. This is unavoidable.

## Verifying Session Persistence

```bash
# Check if session data exists
ls -la .chrome-profile/Default/ | grep -iE "cookies|login|session"

# Check that Current Session / Last Session files exist
ls -la .chrome-profile/Default/Current* .chrome-profile/Default/Last* 2>&1

# Check if Chrome is using the right profile
ps aux | grep "Google Chrome" | grep -v grep | grep user-data-dir
```

Expected: `--user-data-dir=<project-root>/.chrome-profile` in the process args, and `Current Session` / `Last Session` files present (they only exist while Chrome is actively running or was recently open; they're deleted on clean exit).

## Common Pitfalls

### "Sessions were saved yesterday but are gone today"

Root cause: Chrome was killed (`pkill`, Force Quit, system restart) rather than closed normally. On clean exit, Chrome deletes `Current Session` and `Last Session` — the very files it needs to restore tabs and their login cookies. The profile's `Sessions/` directory may still have old session data, but without the pointer files, Chrome ignores them.

**Fix:** Re-login to all services, then always close Chrome normally going forward. The `--restore-last-session` flag handles everything automatically on normal shutdowns.

### "Chrome started but CDP is not responding"

Chrome may be blocked by the macOS Keychain dialog. Check if a dialog is visible. Solution: ensure `--use-mock-keychain` is in `start-chrome.sh`. If already present, kill Chrome with `pkill -f "Google Chrome"` and restart with `bash start-chrome.sh`.

### `restore_on_startup` is not set

The profile's `Preferences` has `restore_on_startup: None` (default = New Tab page). The `--restore-last-session` CLI flag overrides this. If the flag is ever removed, sessions will silently stop restoring even on normal closes.

### `$HOME` resolves to wrong directory in agent environment

The agent's terminal tool sets `$HOME` to `/Users/zall/.hermes/profiles/interviewprep/home` instead of the real home directory (`/Users/zall`). Any script using `$HOME` or Python's `Path.home()` for the profile path will create/write to the wrong directory, and Chrome will start with an empty profile.

**Fix:** The `start-chrome.sh` script uses `SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"` to derive paths relative to itself. Python scrapers use `Path(__file__).resolve().parent.parent` for the same reason. Never use `$HOME` or `Path.home()` for Chrome profile paths.

This is particularly important because the project is open source — absolute paths or `$HOME`-based defaults will break on any machine with a different home directory or terminal environment.

### "Why aren't my regular Chrome logins available?"

The automation uses a separate `--user-data-dir`. The solution is either:
1. Log into job boards once in the automation window (sessions will persist on normal close)
2. Or change `start-chrome.sh` to point to your regular profile (not recommended — pollutes personal profile with automation data)
