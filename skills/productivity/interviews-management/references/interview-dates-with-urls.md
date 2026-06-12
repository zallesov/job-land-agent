# Interview dates with URLs

Use this when interview records store multiple calendar touches.

## Canonical shape
Each `interview_dates_json` item may contain:
- `date`: ISO timestamp for the meeting start time
- `url`: Google Calendar `htmlLink` for the event invite
- `label`: optional short note, e.g. `Technical round`

## Rules
- Keep the timestamp and URL together in the same object.
- Preserve earlier meetings when a later follow-up is added.
- Keep `next_interview_date` aligned with the first upcoming meeting for compatibility.
- Do not treat the URL as a meeting link replacement; it is the calendar invite URL.

## UI expectation
- The dashboard shows the time as a clickable link to the calendar event.
- Manual adds should allow entering time plus optional URL.
