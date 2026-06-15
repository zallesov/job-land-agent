# Calendar dry-run pitfalls for interview tracking

Observed in practice:

- Google Calendar search can return multiple entries for the same process or repeated event copies. Do not assume each row is a distinct interview process.
- A single interview process may have several calendar entries. Keep them as one record and map each meeting time to its own `htmlLink`.
- Use Gmail to confirm the process state and role. Calendar confirms timing, participants, and the invite URL; it does not by itself establish job-title truth.
- Generic meeting titles are not enough to create or rename a process. If the title is only a meeting label, require corroboration from Gmail or the jobs record.
- Not every meeting in the calendar is a job interview. Exclude founder-matching, networking, or other non-hiring meetings unless Gmail or the jobs record explicitly ties them to an interview process.
- In dry runs, report the exact record you would update, the fields you would add, and which calendar URLs support each date before writing anything.
