# Interview dates array handling

## What changed

The interviews table now uses `interview_dates_json` as the canonical container for all matched meeting times in a process.

## Rules

- Store every matched calendar time for a process in `interview_dates_json`.
- Each array item should keep the meeting timestamp and the calendar event URL (`url`), with optional `label` if useful.
- Keep `next_interview_date` updated for compatibility with older UI code.
- When there are multiple meetings:
  - prefer the earliest upcoming date for `next_interview_date`
  - keep the full set in `interview_dates_json`
- Do not lose earlier meetings when a later follow-up is added.
- Use the calendar title, participant names, and calendar event URL (`htmlLink`) to map events to the correct interview record before proposing any update.

## Reconciliation pattern

1. Build a local mapping table of interview record -> calendar events.
2. Verify each match with Gmail or invite body evidence.
3. Write the full date array.
4. Backfill `next_interview_date` if needed for compatibility.
