# Email triage for interview records

Use Gmail threads as the source of truth for interview process state.

## Matching strategy

1. Search by exact company name first.
2. Search by contact person name.
3. Search by contact email address and sender domain.
4. Search by exact subject / calendar title when a company or person name is missing.

## How to resolve state

- Calendar invites only confirm scheduling.
- Recruiter follow-up or rejection emails override a stale calendar-derived status.
- Use the latest substantive recruiter/hiring-team email to decide whether the process is:
  - continuing / awaiting feedback
  - rejected / not moving forward
  - next step scheduled

## What to store in the interview row

- Keep the matching email subject, sender, date, and body excerpt in the record.
- Store multiple matched emails only when they explain the process state or next step.
- Do not add the candidate's own email address to the contacts list.
- Prefer the recruiter / hiring-manager address from the thread over generic calendar-notification addresses.

## Front example pattern

A calendar invite can say the next step is scheduled, but a later recruiter email may say:

- "not the best fit at this time"
- "would love to keep in touch"

In that case, the interview should be marked as rejected / not moving forward, not awaiting feedback.
