# JobLeads Auth Detection Patterns

## How JobLeads handles unauthenticated sessions

JobLeads does NOT redirect to a login wall when the session is unauthenticated.
Instead, it shows a degraded anonymous search page where:

- Company names are hidden as **"Solo para miembros registrados"** (Members only)
- Salary ranges are generic bands (70-100K, 80-120K) rather than precise figures
- The "For You" personalized feed falls back to generic keyword search
- Job detail pages show truncated/redacted descriptions

## Detection methods in the scraper (scripts/providers/jobleads/scrape_jobs.py)

### 1. URL-based (`is_auth_page`)
Checks for login-page URL patterns:
- `/external-home`
- `accounts.google.com`
- `modal=login`
- `sign.in`

Limitation: JobLeads rarely redirects to these; anonymous mode is more common.

### 2. Content-based (`is_unauthenticated`)
Scans the full page HTML for **"solo para miembros registrados"**.
This is the definitive signal — if this phrase appears, the session is unauthenticated
regardless of cookies or URL.

Both checks run immediately after page load in `collect_jobleads()` and exit with code 10
if triggered.

## Why check_auth.py can't catch this

`scripts/providers/jobleads/check_auth.py` only checks for the presence of a session
cookie. The anonymous mode issue occurs even with a valid-looking cookie — the cookie
exists but the server-side session is either expired, invalid, or was never authenticated
in the first place (e.g., the cookie was set by visiting the page anonymously).

A content-based check would require loading the search page and parsing HTML, which
is more expensive than a cookie check but could be added to check_auth.py as a
`--deep` flag.

## Recovery steps

1. User logs in at https://www.jobleads.com/login in the Chrome browser window
2. Verify by navigating to any search page and confirming company names are visible (not "Solo para miembros registrados")
3. Delete any bad jobs scraped while unauthenticated:
   ```bash
   python3 -c "import sqlite3; db=sqlite3.connect('jobs.db'); db.execute(\"DELETE FROM jobs WHERE provider='jobleads'\"); db.commit()"
   ```
4. Re-run scraper: `python3 scripts/scraping_pipeline.py --provider jobleads`
