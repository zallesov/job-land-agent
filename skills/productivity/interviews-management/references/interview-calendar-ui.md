# Interview calendar / dashboard UI notes

Session-derived conventions for the interviews workflow.

## Calendar date objects

- `interview_dates_json` stores an array of date objects.
- Each item should keep:
  - `date` — ISO datetime string
  - `url` — Google Calendar `htmlLink` for the invite
  - `label` — optional short note for the round
- Keep `next_interview_date` aligned for compatibility with older UI code.

## Dashboard editing behavior

- The date column is a link to the calendar event when `url` exists.
- Users add or remove meeting times; the time itself does not need inline editing.
- The comments field should be a multiline textarea.
- Default comments height: 2 rows.
- Cmd+Enter inserts a newline inside comments.
- Plain Enter commits the edit.

## Review workflow

- Build a local mapping table first when reconciling multiple meetings.
- Include timestamp, title, and calendar URL in the table before writing updates.
- Use Gmail/invite evidence to identify the process, then attach the calendar URL to the matching date entry.
