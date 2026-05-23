# CDP Connection Learnings (2026-05-20)

## The `connect_over_cdp` Pattern

All scrapers now use the same pattern:

```python
browser = pw.chromium.connect_over_cdp("http://localhost:9222")
context = browser.contexts[0]
# Close stale pages
for p in list(context.pages):
    try: p.close()
    except: pass
page = context.new_page()
```

This inherits the Chrome profile's cookies, auth tokens, DataDome challenges — no separate browser launch, no headless detection.

## Why CDP over launch_persistent_context

| Approach | DataDome | Auth | Session |
|----------|----------|------|---------|
| `launch_persistent_context` (old) | Blocked (403) | Needs re-auth per run | Separate profile |
| `connect_over_cdp` (new) | Passes (existing cookie) | Inherits Chrome session | Shared profile |

## Sprout-Specific Discoveries

### React Handler vs Playwright click()

The critical discovery: Playwright's `locator.click()` dispatches a synthetic DOM event that React's event delegation system ignores. The button is found, visible, and enabled — but clicking it does nothing. Using `page.evaluate()` to call the native DOM `element.click()` triggers React's synthetic event system properly.

This may apply to OTHER React SPAs with custom event handlers (not just Sprout). When a button that should navigate/open a new tab does nothing on Playwright click, try JS click first.

### Greenhouse ?error=true via Sprout

When Sprout's "View Original" opens a Greenhouse URL, it sometimes adds `?error=true`. The error is cosmetic — Greenhouse checks the Referer header and the cross-origin navigation from Sprout may not send one. The page still loads correctly. The URL with `?error=true` is still valid for dedup.

## Selector Pitfalls

- Playwright does NOT support `textbox` as a locator. Use `input` or `[role="textbox"]`.
- `page.locator('textbox').first` → `TimeoutError: Locator.click: Timeout 30000ms exceeded`
- Correct: `page.locator('input[placeholder="Job Title"]').first`

## Browser Tool Tab Conflicts

When both Hermes `browser_navigate` and Playwright MCP are connected to the same Chrome via CDP, they compete for tab focus. Pages navigate to random URLs, snapshots show wrong content. Use only ONE browser tool at a time for the same Chrome instance.
