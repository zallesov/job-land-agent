---
name: read-web-pages
description: Use when fetching content from web pages that block non-profile browsers (DataDome, Cloudflare, bot detection). Use when a site requires authenticated session cookies to view content.
---

# Read Web Pages via Visible Local Chrome CDP

## Overview

Sites with bot detection (DataDome, Cloudflare) block non-profile browsers. Use the persistent visible Chrome session at `localhost:9222` instead — it has real cookies, real fingerprint, no bot signals.

## When to Use

- Non-profile browser tools get CAPTCHA or "Access temporarily restricted"
- Site requires login (Wellfound, LinkedIn, etc.)
- DataDome / Cloudflare detected
- Need to read a page where auth cookies matter

**Do NOT use non-CDP browser navigation tools.** Use `browser_cdp` for direct browser operations, or a Playwright script that connects over CDP when page text extraction is easier in Python.

## Core Pattern

```python
import asyncio
from playwright.async_api import async_playwright

async def read_page(url: str) -> str:
    async with async_playwright() as p:
        # Attach to running headful Chrome — do NOT launch new browser
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

## Verify Browser is Running

```bash
curl -s http://localhost:9222/json/version | python3 -m json.tool
```

Returns Chrome version info if running. If not running, use the visible-browser auth workflow for the relevant provider.

## Extract Structured Data (Next.js / React apps)

Many SPAs embed JSON in `__NEXT_DATA__`:

```python
import re, json

content = await page.content()  # full HTML
match = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', content, re.DOTALL)
if match:
    data = json.loads(match.group(1))
    # navigate data['props']['pageProps'] for page-specific content
```

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Using non-profile browser tools on bot-protected sites | Use `browser_cdp` or `connect_over_cdp("http://localhost:9222")` |
| Launching new browser instead of attaching | `connect_over_cdp` not `launch()` — new browser has no cookies |
| Fetching with `urllib`/`requests` after getting cookies | DataDome ties cookie to browser fingerprint; raw HTTP requests get 403 |
| Not waiting for JS render | Add `await page.wait_for_timeout(2000)` after `goto` |
| Forgetting to close the page | Always `await page.close()` — leaves tab open in headful browser |
