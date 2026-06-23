# Dashboard cache freshness for interview rows

Observed symptom:
- PocketBase/API has the updated `interview_dates_json` array, but `/interviews` still shows only the old single date in the UI.

Root cause in this profile:
- The Next.js interviews page was serving a stale server-rendered snapshot.
- Client subscription was fine; the page itself needed to opt out of caching.

Fix used:
- In `dashboard/app/interviews/page.tsx` add:
  - `export const dynamic = "force-dynamic";`
  - `export const revalidate = 0;`
  - `unstable_noStore()` / `noStore()` inside the page component

Verification:
1. Confirm the API returns the full array with `GET /api/interviews`.
2. Open `/interviews` in Chrome.
3. Use browser console to inspect the row text for the target company.
4. Hard refresh if the tab was already open before the patch.

Notes:
- If the API shows all dates and the table only shows one, prefer checking page caching before editing the interview record again.
- For multi-date processes, the UI should render every entry in `interview_dates_json`, not just `next_interview_date`.