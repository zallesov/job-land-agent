---
name: run-dashboard
description: Start the job search dashboard and open it in the browser. Triggered by "open dashboard", "run dashboard", "show dashboard", "/run-dashboard".
---

# run-dashboard

## Step 1: Check if already running

```bash
curl -s -o /dev/null -w "%{http_code}" --max-time 3 http://localhost:3000 2>&1
```

If output is `200`, `302`, or `304`: server is healthy, skip to Step 4.
If output is `000` or anything else: server is down or hung, proceed to Step 2.

## Step 2: Clean up stale dashboard processes

```bash
lsof -t -i :3000 | xargs kill -9 2>/dev/null || true
pkill -f 'next dev' 2>/dev/null || true
sleep 1
```

## Step 3: Start the dev server

Run from the current Hermes profile root, not from a developer checkout:

```bash
pnpm run dev
```

Use a background terminal/session for this long-lived command.

Wait for it to be ready:

```bash
for i in $(seq 1 30); do
  code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 2 http://localhost:3000 2>/dev/null)
  echo "$code" | grep -q "200\|302\|304" && echo "READY" && break
  sleep 1
done
```

If not ready after 30s: show the dev server output and report the error.

## Step 4: Open in browser

Open `http://localhost:3000` in the visible Chrome CDP session. Never use the non-CDP navigation tool in this agent.

```python
browser_cdp(method="Target.createTarget", params={"url": "http://localhost:3000"})
```

Report: "Dashboard is running at http://localhost:3000"
