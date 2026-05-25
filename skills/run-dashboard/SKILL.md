---
name: run-dashboard
description: Start the job search dashboard and open it in the browser. Triggered by "open dashboard", "run dashboard", "show dashboard", "/run-dashboard".
---

# run-dashboard

## Step 1: Check if already running

```bash
curl -s http://localhost:3000 > /dev/null 2>&1 && echo "RUNNING" || echo "NOT_RUNNING"
```

If `RUNNING`: skip to Step 3.

## Step 2: Start the dev server

```bash
cd dashboard && npm run dev > /tmp/dashboard.log 2>&1 &
```

Wait for it to be ready:

```bash
for i in $(seq 1 20); do curl -s http://localhost:3000 > /dev/null 2>&1 && echo "READY" && break; sleep 1; done
```

If not ready after 20s: show last lines of `/tmp/dashboard.log` and report the error.

## Step 3: Open in browser

Navigate to `http://localhost:3000` using `browser_navigate`.

Report: "Dashboard is running at http://localhost:3000"
