# PocketBase dashboard verification for interviews

Use this when interview records are written to PocketBase but the dashboard looks stale.

## What to verify

1. Read the record back from PocketBase via the dashboard API (`/api/interviews` or the relevant collection endpoint).
2. Confirm `interview_dates_json` is stored as a JSON array, not a flattened string or single date.
3. Confirm each array item has at least `date`; add `label` and `url` when available.
4. If the dashboard still shows only one date, treat the page as potentially stale until a hard refresh / reopen proves otherwise.

## Rendering notes

- The interviews table normalizes PocketBase JSON fields to strings before passing them to the client.
- `InterviewDatesCell` renders every parsed entry from `interview_dates_json`.
- `next_interview_date` is a separate field; it does not replace the array.

## Practical rule

When updating multi-step interview processes, always check the canonical source (`interview_dates_json`) first and use the dashboard view only as a display check, not as proof of persistence.