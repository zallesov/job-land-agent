# ATS Direct API Access Patterns

When checking whether a company has remote-eligible roles, avoid browser navigation. Hit the underlying ATS API directly — it's 5-10x faster and returns structured JSON.

## Greenhouse

API endpoint: `https://boards-api.greenhouse.io/v1/boards/{board}/jobs?content=true`

The `{board}` name is the subdomain in the career page URL:
- `boards.greenhouse.io/parloa` → board = `parloa`
- `boards.greenhouse.io/nscale` → board = `nscale`

### Bash one-liner to find remote roles:
```bash
curl -s "https://boards-api.greenhouse.io/v1/boards/{board}/jobs?content=true" | \
  python3 -c "
import json, sys
data = json.load(sys.stdin)
for j in data.get('jobs', []):
    loc = j.get('location', {}).get('name', '')
    if any(w in loc.lower() for w in ['remote', 'europe', 'germany', 'emea', 'worldwide']):
        print(f\"{j['title']} | {loc} | {j['absolute_url']}\")
"
```

### Known Greenhouse boards (Berlin/European AI companies):
| Company | Board | Example |
|---------|-------|---------|
| Parloa | parloa | `boards.greenhouse.io/parloa` |
| Nscale | nscale | `boards.greenhouse.io/nscale` |
| SoundCloud | soundcloud | `boards.greenhouse.io/soundcloud` |
| Contentful | contentful | `boards-api.greenhouse.io/v1/boards/contentful` |

## Ashby

API endpoint: `https://jobs.ashbyhq.com/api/non-user-list?ashby_job_board_domain={board}`

Board names are NOT predictable from domain names:
- `hcompany.ai` → board = `hcompany`
- `v7labs.com` → board = `v7labs`
- Some companies use subdomain aliases

### Finding the Ashby board name:
Navigate to the company's careers page via browser, then use browser_console to extract:
```js
document.querySelector('a[href*="jobs.ashbyhq.com"]')?.href
```

### Bash one-liner for Ashby (once board is known):
```bash
curl -s "https://jobs.ashbyhq.com/api/non-user-list?ashby_job_board_domain={board}" | \
  python3 -c "
import json, sys
data = json.load(sys.stdin)
for j in data.get('jobs', []):
    loc = j.get('location', '')
    if any(w in loc.lower() for w in ['remote', 'europe', 'germany', 'emea']):
        print(f\"{j['title']} | {loc} | https://jobs.ashbyhq.com/{board}/{j['id']}\")
"
```

## Lever

API endpoint: `https://api.lever.co/v0/postings/{board}`

Board name is the subdomain: `jobs.lever.co/v7` → board = `v7`

## Rippling (ATS)

API endpoint varies. Often: `https://ats.rippling.com/{company}/jobs` (HTML, not API).

No known public JSON API. Must scrape HTML or use browser.

## Workday / Ice

No public API. Heavily JS-rendered, frequently CAPTCHA-protected (DataDome). Skip these companies for ad-hoc scraping — they're handled by the daily scraper scripts.

## Decision Flow

```
Company discovered via Explee
  ↓
Open careers page in browser (browser_navigate)
  ↓
Check which ATS platform (Greenhouse/Ashby/Lever/Workday/Custom)
  ↓
If Greenhouse/Ashby/Lever: use direct API curl → filter for remote → done in <5s
  ↓
If Workday/Ice: skip, handled by daily pipeline scripts
  ↓
If Custom: browser_snapshot + extract job list, slower but only option
```

## Speed Comparison

| Method | Per company | 80 companies |
|--------|------------|-------------|
| Greenhouse API (curl) | ~2s | ~3 min |
| Ashby API (curl) | ~3s | ~4 min |
| Browser navigate + snapshot | ~15-30s | ~20-40 min |
| Subagent (15 companies each) | TIMEOUT (600s) | FAIL |
