---
name: read-web-pages
description: Use when fetching content from web pages that block non-profile browsers (DataDome, Cloudflare, bot detection). Use when a site requires authenticated session cookies to view content. Canonical reference for launching Chrome and choosing agent-browser vs raw CDP.
---

# Read Web Pages via Visible Local Chrome CDP

## Overview

Sites with bot detection (DataDome, Cloudflare) block headless / freshly-launched
browsers. Use the persistent **visible** Chrome at `localhost:9222` — it has real
cookies, a real fingerprint, and no bot signals. Drive it with the **agent-browser**
CLI for normal work, and drop to raw CDP only for tricky React-controlled forms.

## When to Use

- Headless / non-profile browser gets CAPTCHA or "Access temporarily restricted"
- Site requires login (Wellfound, LinkedIn, etc.)
- DataDome / Cloudflare detected
- Need to read a page where auth cookies matter

## 1. Launch Chrome (once per machine/boot)

```bash
bash agent/start-chrome.sh
```

This launches **visible** Chrome with:
- `--remote-debugging-port=9222` — CDP endpoint
- `--user-data-dir=agent/.chrome-profile` — persistent profile (cookies, localStorage, login)
- `--disable-blink-features=AutomationControlled` — hides `navigator.webdriver`
- `--use-mock-keychain` — encrypts cookies with a fixed key, **not** the OS keychain,
  so the profile is portable across machines/OS (Mac → Linux server)

It does **not** pass `--enable-automation` — that flag sets `navigator.webdriver=true`
and is an instant bot signal. Do not re-add it.

Verify it is up:

```bash
curl -s http://localhost:9222/json/version | python3 -m json.tool
```

Expect `"Browser": "Chrome/<version>"` (NOT `HeadlessChrome`). If not running, launch it.

Confirm the stealth fingerprint is clean:

```bash
agent-browser close --all
agent-browser --cdp 9222 eval 'JSON.stringify({webdriver:navigator.webdriver, headless:navigator.userAgent.includes("Headless")})'
# expect {"webdriver":false,"headless":false}
```

## 2. Drive it with agent-browser (PRIMARY path)

**Always pass `--cdp 9222` on every command.** Without it, agent-browser launches its
own bundled **headless** Chrome on a random port — invisible to the user AND instantly
blocked by DataDome (`navigator.webdriver=true`, `HeadlessChrome` UA).

The agent-browser daemon caches the first connection. If a previous run used the wrong
browser, reset it once:

```bash
agent-browser close --all            # drop the cached daemon
agent-browser --cdp 9222 open wellfound.com/jobs
agent-browser --cdp 9222 snapshot -i # accessibility tree with @eN refs
agent-browser --cdp 9222 get text @e1
agent-browser --cdp 9222 click @e5
agent-browser --cdp 9222 fill  @e3 "text"
```

`snapshot -i` returns interactive elements with compact `@eN` refs (~200-400 tokens)
instead of raw HTML — use refs from the latest snapshot for click/fill/type.

### Common mistakes

| Mistake | Fix |
|---------|-----|
| Omitting `--cdp 9222` | agent-browser uses its own headless browser → invisible + DataDome block |
| `connect 9222` then `open` | `connect` does NOT bind the `default` session; use `--cdp 9222` per command |
| Stale daemon from a prior run | `agent-browser close --all` once, then re-run with `--cdp 9222` |
| Rapid open/close loops | DataDome IP-scores rapid activity → temporary block; slow down |
| Launching a new browser to "get cookies" | new browser has none; only the 9222 profile has the session |

## 3. Raw CDP / Playwright (FALLBACK only)

Use raw CDP for React-controlled form fields where a plain `fill` does not stick
(native value setter + input/change events — see
`apply-job/references/wellfound-cdp-templates.md`), or when Python text extraction is
easier. Attach over CDP — never `launch()` a new browser.

```python
import asyncio
from playwright.async_api import async_playwright

async def read_page(url: str) -> str:
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp("http://localhost:9222")
        ctx = browser.contexts[0]          # reuse existing context with cookies
        page = await ctx.new_page()
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(2000)  # let JS render
        text = await page.inner_text("body")
        await page.close()
        return text

content = asyncio.run(read_page("https://wellfound.com/jobs/123-some-role"))
```

### Extract structured data (Next.js / React apps)

Many SPAs embed JSON in `__NEXT_DATA__`:

```python
import re, json
content = await page.content()
m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', content, re.DOTALL)
if m:
    data = json.loads(m.group(1))   # navigate data['props']['pageProps']
```

| Mistake | Fix |
|---------|-----|
| Launching a new browser instead of attaching | `connect_over_cdp` not `launch()` |
| Fetching with `urllib`/`requests` after getting cookies | DataDome ties the cookie to the browser fingerprint; raw HTTP gets 403 |
| Not waiting for JS render | `await page.wait_for_timeout(2000)` after `goto` |
| Leaving tabs open | always `await page.close()` |

## Choosing: agent-browser vs raw CDP

- **agent-browser `--cdp 9222`** — default for navigate, read, snapshot, click, fill,
  screenshot, and session export. High-level, compact, less to get wrong.
- **raw CDP (`Runtime.evaluate`) / Playwright** — only for React fields that ignore
  normal fills, bulk one-shot DOM scripts, or Python-side extraction. Both target the
  **same** 9222 Chrome.

## Provider workflows

This skill is the generic browser runtime. Provider-specific scraping lives in its own
skills — e.g. the Wellfound pipeline (`wellfound-flow` → `wellfound-check-auth`,
`wellfound-login`, `wellfound-parse-jobs`, `wellfound-enrich-jobs`). Two reusable facts
those skills rely on:

- **Feeds are often client-fetched**: a page's `__NEXT_DATA__` may hold zero list items —
  parse the **rendered DOM** after scroll, not the SSR payload.
- **SSR vs client on detail pages**: `__NEXT_DATA__` carries server metadata (title,
  description, compensation); links that render after hydration (e.g. an external apply
  URL) are only in the live DOM. Use SSR for metadata, rendered DOM for the rest.

## Session portability (local → server)

The login lives in two interchangeable places:

1. **Whole profile dir** `agent/.chrome-profile` — copy it to the server and launch
   Chrome there with the same `--user-data-dir`. Portable across OS **because** of
   `--use-mock-keychain` (without it, macOS-encrypted cookies will not decrypt on Linux).
2. **Exported state JSON** — cookies + localStorage + sessionStorage:
   ```bash
   agent-browser --cdp 9222 state save wellfound-auth.json   # export
   agent-browser --state wellfound-auth.json --user-agent "<same UA>" open wellfound.com/jobs
   ```

Verified locally: the session survives an **IP change** (VPN country switch) and a
**Chrome restart** — the `datadome` / `cf_clearance` / `_wellfound` cookies are not
hard-bound to the exact IP. On a server still:

- keep the **same User-Agent** (`--user-agent`),
- prefer a **residential-ish IP / proxy** (`--proxy`); bare datacenter IPs get scored
  harder by DataDome and may re-challenge,
- expect the clearance token to expire eventually — have a re-login fallback.
