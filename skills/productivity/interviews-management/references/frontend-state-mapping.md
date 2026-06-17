# Interviews dashboard state mapping

Use this mapping when writing or reviewing interview records so the stored values match the dashboard controls.

## Stored values vs UI labels

status (stored in PocketBase)
- `applied` → Applied
- `in_process` → In Process
- `rejected` → Rejected
- `offer` → Offer

interview_status (stored in PocketBase)
- `scheduled` → Scheduled
- `awaiting_response` → Awaiting Feedback
- `rejected` → Rejected

## Notes

- The dashboard selects and filters on the stored machine values, not the display labels.
- When evidence says "interviewing", map it to `in_process` unless the database schema has been extended.
- When evidence says "awaiting feedback", map it to `awaiting_response`.
- After writing interview dates or status changes, verify the `/interviews` page reflects the change; if the page looks stale, refresh the page or check the API response directly.
- Interview date arrays are rendered from `interview_dates_json` as multiple entries; each item should be `{date, label?, url?}`.
