# Codex Chrome Extension

Announced via YouTube demo (May 2026). Codex can control real Chrome without
Playwright — it uses an official Chrome extension.

## How it works

- Creates its own Chrome tab group, separate from the user's tabs
- Works in the background — user can keep working undisturbed
- Same profile, session, cookies, logged-in apps as the user
- Can open multiple tabs in parallel and script repetitive actions
- Can reason while browsing to verify it's on the right track
- Combines with other Codex plugins (email, spreadsheets, etc.)

## vs. Playwright / Selenium

No Playwright needed. The extension controls real Chrome directly via CDP-like
integration. No separate driver, no headless mode issues, no cookie/auth sync
problems.

## vs. computer_use

`computer_use` takes over the whole screen with screenshot→reason→click loops.
The Chrome extension is more efficient:
- Doesn't block the user's desktop
- Can script actions without visual reasoning overhead
- Works across multiple tabs in parallel
- Uses code execution to drive the browser programmatically

## vs. in_app_browser

`in_app_browser` is great for local dev tasks with annotations. The Chrome
extension is better for:
- Real logged-in sessions (existing cookies/auth)
- Multi-tab parallel work
- Leveraging full browser features

## Feature flags

```
browser_use          stable  # Built-in browser engine
browser_use_external stable  # Chrome extension control
in_app_browser       stable  # Browser inside Codex app
computer_use         stable  # Full desktop control
```

All four are stable and enabled by default in Codex 0.130.0+.
