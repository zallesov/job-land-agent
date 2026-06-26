#!/usr/bin/env python3
"""
Load a saved browser session (cookies + localStorage) into the running CDP Chrome.

Used on the remote/container side of path B: a session exported locally with
`agent-browser --cdp 9222 state save session.json` is carried over and injected into the
server's authenticated Chrome so it can browse as the user.

The state file is Playwright storageState shape:
  {"cookies": [...], "origins": [{"origin": "...", "localStorage": [{"name","value"}]}]}

Chrome must already be running with CDP (bash start-chrome.sh). This attaches over CDP
(does not launch a browser) and writes cookies + localStorage into the live context.

Usage:
  python3 scripts/load_session.py session.json [--cdp http://127.0.0.1:9222] [--verify URL]
"""
import argparse, asyncio, json, sys
from pathlib import Path
from playwright.async_api import async_playwright

SAMESITE = {"lax": "Lax", "strict": "Strict", "none": "None",
            "no_restriction": "None", "unspecified": "Lax"}


def normalize_cookie(c):
    out = {k: c[k] for k in ("name", "value", "domain", "path") if k in c}
    if "expires" in c and c["expires"] not in (None, -1):
        out["expires"] = c["expires"]
    out["httpOnly"] = bool(c.get("httpOnly", False))
    out["secure"] = bool(c.get("secure", False))
    ss = str(c.get("sameSite", "Lax")).lower()
    out["sameSite"] = SAMESITE.get(ss, "Lax")
    return out


async def run(args):
    state = json.loads(Path(args.state).read_text())
    cookies = state.get("cookies", [])
    origins = state.get("origins", [])

    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp(args.cdp)
        ctx = browser.contexts[0]

        if cookies:
            await ctx.add_cookies([normalize_cookie(c) for c in cookies])
        print(f"loaded {len(cookies)} cookies")

        ls_total = 0
        for o in origins:
            origin = o.get("origin")
            items = o.get("localStorage", [])
            if not origin or not items:
                continue
            page = await ctx.new_page()
            try:
                await page.goto(origin, wait_until="domcontentloaded", timeout=20000)
                await page.evaluate(
                    "items => { for (const {name, value} of items) localStorage.setItem(name, value); }",
                    items)
                ls_total += len(items)
            except Exception as e:
                print(f"  localStorage {origin}: {str(e)[:120]}", file=sys.stderr)
            finally:
                await page.close()
        print(f"loaded {ls_total} localStorage items across {len(origins)} origins")

        if args.verify:
            page = await ctx.new_page()
            await page.goto(args.verify, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(1500)
            title = await page.title()
            await page.close()
            print(f"verify {args.verify} -> {title}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("state")
    ap.add_argument("--cdp", default="http://127.0.0.1:9222")
    ap.add_argument("--verify", default=None, help="URL to open after load to confirm auth")
    asyncio.run(run(ap.parse_args()))


if __name__ == "__main__":
    main()
