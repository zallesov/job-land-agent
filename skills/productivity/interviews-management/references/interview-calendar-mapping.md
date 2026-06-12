# Calendar-to-interview mapping notes

Use this when interview records now carry multiple interview dates.

## Goal
Build a review table first, then update the DB only after the mapping is clear.

## Mapping rule
For each interview process:
- inspect every interview date in the array
- search Calendar for each date in the same window
- match meetings by company name first, then by people met, then by explicit invite/body clues
- treat secondary contacts in the same process as additional evidence, not separate processes

## What counts as a match
Use the strongest explicit evidence available:
1. company name in the invite, body, or Gmail thread
2. interviewer / recruiter names
3. domain or sender email
4. title only, if there is no better clue

## Calendar payload to keep
When the event is identified, capture at least:
- `date` / start time
- `url` (Google Calendar `htmlLink`)
- optional `label`
- optional `title` / `location` if useful for provenance

## Output before DB writes
Always produce a local review table with:
- interview record id
- company/process name
- all matched calendar timestamps
- event titles
- event URLs
- a short note explaining the evidence

## Cautions
- Do not collapse multiple dates into one when the interview process has multiple calendar touchpoints.
- Do not use generic meeting titles alone if the invite body or Gmail thread identifies the real company/person.
- Leave company_name blank in the review table if the DB record is still blank and evidence is incomplete.
- Calendar confirms timing; Gmail or invite body usually confirms the process identity.
