# Playwright MCP Browser Persistence

Codex spawns a Playwright MCP server (`@anthropic/playwright-mcp`) for browser automation.
The server launches system Chrome with a persistent `userDataDir`, so cookies, localStorage,
sessions, and extensions survive across `codex exec` invocations.

## How it works

Playwright MCP uses `browserType.launchPersistentContext(userDataDir, options)` under the hood.
This is equivalent to launching Chrome with `--user-data-dir=<path>` — the full browser profile
(including auth cookies) is loaded from disk on startup and saved on shutdown.

## Finding the current userDataDir

The browser state file reveals the active path:

```
~/.hermes/profiles/<profile>/home/Library/Caches/ms-playwright/b/browser@<hash>
```

Example content:
```json
{
  "browser": {
    "launchOptions": {
      "channel": "chrome",
      "headless": false,
      "userDataDir": "/Users/zall/.../ms-playwright/mcp-chrome-990c176"
    }
  }
}
```

The `Default/Cookies` file inside that directory confirms auth state is persisted.

## Explicit configuration

### Via Codex config (`~/.codex/config.toml`)

```toml
[playwright]
user_data_dir = "/Users/zall/interviews/.playwright-mcp/chrome-profile"
```

### Via Playwright MCP server args (standalone, outside Codex)

```sh
npx @anthropic/playwright-mcp \
  --user-data-dir /path/to/chrome-profile \
  --channel chrome \
  --no-headless
```

### Via Hermes mcp_servers config

```yaml
mcp_servers:
  playwright:
    command: "npx"
    args:
      - "-y"
      - "@anthropic/playwright-mcp"
      - "--user-data-dir"
      - "/Users/zall/interviews/.playwright-mcp/chrome-profile"
```

## Important: profile locking

Chrome locks its profile directory. Only ONE instance can use a `userDataDir` at a time.
If a cron job fires while a manual scrape is running (or two crons overlap), the second
instance fails with a profile lock error.

Guard with a lockfile in cron wrappers:

```bash
LOCKFILE="/path/to/.scrape.lock"
exec 9>"$LOCKFILE"
if ! flock -n 9; then
  echo "Another scrape is already running, exiting."
  exit 0
fi
codex exec ...
```

## Stable path recommendation

By default, the `userDataDir` lives under the Hermes profile home cache
(`~/.hermes/profiles/<name>/home/Library/Caches/ms-playwright/`). This is fragile:
profile resets, `npx` cache cleans, or npm cache purges can delete it — and all
your auth cookies with it.

Move to a stable, non-cache location:

```bash
mv ~/.hermes/profiles/interviewprep/home/Library/Caches/ms-playwright/mcp-chrome-990c176 \
   /Users/zall/interviews/.playwright-mcp/chrome-profile
```

Then update the `user_data_dir` in Codex config to point there.

## Auth expiry detection

For sites that require authentication, build an auth check into the scraper script.
When the scraper detects a login redirect, fail fast with a clear message so the
operator knows to re-authenticate in the visible browser. Example (from the
Greenhouse scraper):

```js
if (/\/users\/sign_in/.test(page.url())) {
  throw new Error(
    `Not authenticated; sign in in the Playwright browser and retry.`
  );
}
```
