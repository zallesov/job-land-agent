# Session Learnings — 2026-05-20

## DataDome Confirmation

```bash
$ curl -sI https://wellfound.com/jobs
HTTP/2 403
set-cookie: datadome=Ps4b07b0lcPbZo57sXAEOBTyDJRkjrEGskpKVq3L23GSU9OVOc4jWn2DQrjSJ6c9...
```

Plain HTTP client → immediate 403. Only CDP through existing Chrome works.

## Playwright MCP ERR_ABORTED Recovery

When `mcp_playwright_browser_navigate` returns `net::ERR_ABORTED`:

```
Error: browserBackend.callTool: net::ERR_ABORTED at https://wellfound.com/jobs
```

Workaround: navigate to `about:blank` first, then to WellFound. This clears navigation state.

## Filters Modal Destroys Search State

Clicking "Filters" button → 0 job links after modal close:

```
Scroll 1: 0 job links visible
Scroll 2: 0 job links visible
```

Root cause: WellFound's Filters modal resets the client-side search state on open. Never automate the Filters button.

## Remote Toggle Disabled with Saved Search

```
locator resolved to <button disabled type="button" class="styles_component__kQDF2">…</button>
- element is not enabled
```

The Remote/On-site toggle is `disabled` when a saved search is active. Workaround: update saved search manually once.

## Browser Tool Tab Conflicts

When both `browser_navigate` and Playwright MCP share Chrome:
- Pages navigate to random sites (antler.co, goyaa.io, heylama.com)
- `browser_snapshot` shows content from wrong URLs
- `Target.getTargets` shows pages with stale URLs

Solution: the Python `connect_over_cdp` script creates its own page and doesn't interfere. For interactive work, use only ONE browser tool at a time.

## Scrape Performance (2026-05-20)

- Saved search: Full Time, Berlin, Software Engineer + AI Engineer + Founding Engineer roles
- Jobs loaded: 165 links, 110 unique after dedup (no filters applied)
- Scroll iterations: 13 (stabilized at 165)
- Enrichment time: ~5-8s per job detail page
