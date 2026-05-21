# CDP Migration Pattern for Job Scrapers

All job scrapers (WellFound, Greenhouse, JobLeads) now use `connect_over_cdp` instead of `launch_persistent_context`.

## Why

- **One Chrome, one profile.** No duplicate Chromium instances competing for the same `~/.interviews-browser-profile` directory.
- **DataDome / bot detection.** WellFound uses DataDome — `curl` and plain headless Playwright get HTTP 403. CDP rides on the already-passed bot challenge in the user's real Chrome session.
- **Auth persistence.** Google OAuth tokens, session cookies, and saved search config live in the Chrome profile. They persist across runs automatically.
- **No `--headless` flag needed.** CDP connects to whatever state the user's Chrome is in (headless or visible).

## Migration Checklist

For any new scraper joining the pipeline, follow this pattern:

1. **Replace launch code:**

```python
# OLD
ctx = pw.chromium.launch_persistent_context(
    str(args.browser_profile),
    channel="chrome",
    headless=args.headless,
    ...
)
page = ctx.pages[0] if ctx.pages else ctx.new_page()

# NEW
browser = pw.chromium.connect_over_cdp(args.cdp_url)
context = browser.contexts[0]
page = context.new_page()
```

2. **Replace close calls:** `ctx.close()` → `browser.close()`

3. **Add `--cdp-url` argument:**

```python
parser.add_argument("--cdp-url", default="http://localhost:9222",
                    help="CDP endpoint (default: http://localhost:9222)")
```

4. **Deprecate old flags:**

```python
parser.add_argument("--headless", action="store_true",
                    help="[DEPRECATED] CDP uses existing Chrome — ignored")
parser.add_argument("--browser-profile", type=Path, default=DEFAULT_PROFILE,
                    help="[DEPRECATED] CDP connection uses existing Chrome profile")
```

5. **Remove `args.browser_profile.mkdir()`** — no profile directory needed.

6. **Update print statement:** `print(f"CDP: {args.cdp_url}")` instead of `print(f"Browser profile: ...")`.

7. **Update skill doc:** Remove `--headless`, add `--cdp-url`, document pre-flight Chrome check.

## Pre-Flight for All Scrapers

```bash
curl -s http://localhost:9222/json/version || echo "NOT_RUNNING"
```

User runs `~/start-chrome.sh` if not running.
