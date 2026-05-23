# Hermes Browser Infrastructure for Research

## How the Browser Actually Works (Local, Headless Chromium)

Hermes does NOT use Browserbase or any cloud browser. It runs a local headless Chromium via `agent-browser`.

### Local Headless Chromium (how research browsing works)

- **Browser engine**: Local headless Chromium, launched via `npx agent-browser`
- **You see**: Nothing locally. No Chrome window, no Dock icon.
- **User agent**: Reports `HeadlessChrome/...` — this is normal
- **Capabilities**: Full Chrome engine — JS rendering, DOM interaction, click/scroll/type
- **NO cloud service**: No Browserbase, BrowserUse, or Nous cloud provider configured
- **PATH**: Chromium binary managed by `npx` / npm

### Playwright (how application filling works)

- **Script**: `/Users/zall/interviews/scripts/apply_job_filler.py`
- **Mode**: `headless=False` — visible Chrome window
- **When**: Only during the `apply-job` skill workflow
- **This is the only way to see a visual browser**

## Why You Don't See a Window During Research

The research browser (agent-browser) is headless by default. The page loads, renders, runs JS, and can be queried — but nothing renders to your screen. This is correct and intended.

To check it's working:
- The `browser_navigate` response returns a page title, URL, and element snapshot
- `browser_console(expression=...)` runs JS in the page context and returns results
- `browser_vision(question=...)` takes a screenshot and analyzes it

## Two Browser Code Paths

| Workflow | Tool | Visible? | Engine |
|---|---|---|---|
| Research | Hermes browser tool (`browser_navigate`, etc.) | No (headless) | Local agent-browser Chromium |
| Apply | Playwright script (`apply_job_filler.py`) | Yes (headed) | Local system Chrome/Chromium |

## Cloud Provider: NONE

Verified:
- `BROWSERBASE_API_KEY` — commented out in `~/.hermes/.env`
- `BROWSER_USE_API_KEY` — not set
- `NOUS_USER_TOKEN` — not set
- `_get_cloud_provider()` in browser_tool.py returns None
- `_is_local_mode()` returns True

## Pitfalls

### Persistent Cookie Hijacking (Wellfound / other logged-in sessions)

The headless browser retains cookies across sessions. If a previous navigation logged into a site (e.g., Wellfound/AngelList), subsequent `browser_navigate()` calls to unrelated URLs may silently redirect to the logged-in session.

**Symptoms:**
- `browser_navigate("https://some-job-board.com")` returns a Wellfound jobs page
- Page title is "Jobs" or shows your profile avatar
- Snapshot shows "Sign in to Chrome", "Ready to interview", or job listings you didn't request

**Fix:**
1. Kill the agent-browser process and restart: `pkill -f agent-browser && sleep 2`
2. Then re-navigate — a fresh browser session starts with no cookies

**Prevention:** If you know the browser visited a login-walled site earlier in the session, navigate to a neutral page first (`browser_navigate("https://example.com")`) before the real target, or kill + restart agent-browser between unrelated tasks.

## Getting Visibility During Research

Options (in order of practicality):
1. **browser_vision()** — Take a screenshot and have the agent describe what it sees
2. **browser_console()** — Run JS expressions to inspect DOM state, check page title, count elements
3. **Switch to Playwright** — Write a temporary script using Playwright with `headless=False` for a specific research task
4. **Configure agent-browser headed** — Not currently set up; would require modifying the Hermes browser config

## Verification (check yourself in a terminal)

```bash
# Check if Browserbase is configured:
grep BROWSERBASE_API_KEY ~/.hermes/.env
# Returns nothing or commented line -> not active

# Check the browser tool's local/cloud resolution:
grep -n "_is_local_mode\|_get_cloud_provider" ~/.hermes/hermes-agent/tools/browser_tool.py | head -5

# Check running Chromium processes:
ps aux | grep -i chrom | grep -v grep
```
