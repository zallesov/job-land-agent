# PocketBase interview dry-run and write pattern

Use this when the user asks to review calendar/Gmail evidence before updating interview records.

## Pattern

1. Read Calendar first for all matching events in the target time window.
2. Read Gmail threads for the same companies/people to resolve status and role.
3. Build a proposed write set per company/process:
   - company_name
   - job_title
   - status
   - interview_status
   - next_interview_date
   - interview_dates_json
   - contacts_json
   - emails_json
   - comments
4. Show the proposed changes to the user if anything is inferred or ambiguous.
5. Only write after the user explicitly says to proceed.

## Practical notes

- Calendar may contain duplicate or overlapping events for the same process. Keep each unique meeting in interview_dates_json, but do not create multiple interview records for one process.
- Use htmlLink as the calendar URL when storing meeting evidence.
- Treat the latest explicit Gmail evidence as the tie-breaker when status differs from Calendar.
- The active profile uses PocketBase records; write through the existing pb_client helpers / pipeline scripts, not raw SQL.
- Do not treat generic calendar titles as job titles.
- Keep a short dry-run table when many interviews change at once.
