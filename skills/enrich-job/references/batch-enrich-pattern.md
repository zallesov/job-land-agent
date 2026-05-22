# Batch Enrich Pattern (proven)

Exact Python/terminal patterns from the 2026-05-21 session that successfully enriched 15/18 jobs.

## Step 1: Fetch all via Jina

Use `execute_code` with `terminal()` for curl calls:

```python
from hermes_tools import terminal, write_file
import json, time

# Get job list from DB
out = terminal("sqlite3 /Users/zall/interviews/jobs.db \"SELECT id, url FROM jobs WHERE (description IS NULL OR trim(description) = '') AND status != 'deleted' ORDER BY id;\"")
lines = [l for l in out["output"].strip().split("\n") if "|" in l]

results = {}
for line in lines:
    job_id, url = line.split("|", 1)
    
    # Skip obviously broken URLs
    if 'Error' in url or 'jobExpired=True' in url or 'view=board' in url:
        results[job_id] = {"status": "failure", "error": "broken url", "url": url}
        continue
    
    jina_url = f"https://r.jina.ai/{url}"
    out = terminal(f"curl -sL --max-time 30 '{jina_url}' -H 'Accept: text/plain' 2>&1 | head -c 8000", timeout=35)
    content = out.get("output", "")
    
    if not content or len(content) < 100:
        results[job_id] = {"status": "failure", "error": "extraction failed", "url": url}
    else:
        results[job_id] = {"status": "raw", "url": url, "content": content[:4000]}
    
    time.sleep(0.5)

write_file("/Users/zall/interviews/tmp/enrich_raw.json", json.dumps(results, indent=2, ensure_ascii=False))
```

## Step 2: Parse and clean

Read the raw JSON with `strict=False` to handle control characters:

```python
import json, re

with open("/Users/zall/interviews/tmp/enrich_raw.json", "r") as f:
    raw = json.loads(f.read(), strict=False)

def clean_title(t):
    if not t: return t
    m = re.match(r'^Stellenangebot\s+(.+?)\s+bei\s+\S+', t)
    if m: t = m.group(1)
    t = re.sub(r'\s*\|\s*Jobs at .+$', '', t)
    t = re.sub(r'\s*\|\s*\S+\s*$', '', t)
    return t.strip()

def clean_desc(content):
    desc = content
    desc = re.sub(r'Title:\s*.+?\n\n?', '', desc)
    desc = re.sub(r'URL Source:\s*.+\n?', '', desc)
    desc = re.sub(r'Markdown Content:\s*', '', desc)
    desc = re.sub(r'\n{3,}', '\n\n', desc)
    return desc.strip()[:2000]
```

## Step 3: Generate SQL and update

```python
for job_id_str, data in parsed.items():
    if data["status"] != "success": continue
    
    title = clean_title(data.get("title") or "")
    desc = clean_desc(data.get("description") or "")
    apply_url = data.get("apply_url") or data.get("url", "")
    
    title_s = title.replace("'", "''")
    desc_s = desc.replace("'", "''")
    
    sql = f"UPDATE jobs SET title='{title_s}', description='{desc_s}', apply_url='{apply_s}', updated_at=datetime('now') WHERE id={jid};"
    sqls.append(sql)

with open("/Users/zall/interviews/tmp/enrich_updates.sql", "w") as f:
    f.write("\n".join(sqls))

terminal("sqlite3 /Users/zall/interviews/jobs.db < /Users/zall/interviews/tmp/enrich_updates.sql")
```

## Step 4: Browser fallback for Ashby failures

For jobs where Jina title = "Jobs" (Ashby blank page) or desc < 100 chars, use browser:

```
browser_navigate(url)
browser_snapshot(full=true)
```

Check for "Job not found" heading. If found, mark as dead. Otherwise extract from accessibility tree.

Update via SQL:

```sql
UPDATE jobs SET description='URL_ERROR: job not found on Ashby', updated_at=datetime('now') WHERE id=<id>;
```
