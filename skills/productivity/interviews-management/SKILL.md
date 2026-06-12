---
name: interviews-management
description: "Manual interview-process tracking from Gmail, Calendar, LinkedIn, Telegram, and job DB with compact evidence and clean titles."
version: 1.0.0
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [interviews, recruiting, gmail, calendar, linkedin, telegram, tracking, jobs]
---

# Interviews Management

Use this skill to update one interview-process record per company/process.

## References

- `references/interview-evidence-extraction.md` — search order, company-name permutations, contact filters, and compact evidence formatting.
- `references/interview-dates-array.md` — canonical handling for multi-meeting interview processes, including calendar event URLs in `interview_dates_json` and legacy compatibility with `next_interview_date`.
- `references/interview-calendar-mapping.md` — local review-table pattern for mapping every interview date to its matching calendar event URL and title before any DB write.
- `references/interview-calendar-ui.md` — calendar URL-backed interview dates, dashboard editing behavior, and comments textarea conventions.
- `references/interview-dates-with-urls.md` — date/url schema for calendar-backed interview entries and dashboard expectations.

## Core model

- One record represents the whole process for a company/role, not a single meeting.
- The goal is to reduce noise and keep the status of the process easy to navigate.
- Update records only when the user explicitly asks for it.

## Manual-only workflow

This skill is executed manually.

Typical prompts:
- "Update interview process for company X"
- "Check Gmail for company X"
- "Check calendar for company X"
- "Use the email thread for company X and update the process"

Do not poll in the background. Do not auto-sync.

## Collection workflow

For a given company/process, actively collect evidence from multiple places:

1. Gmail
2. Calendar
3. Jobs table

Use company-name permutations when searching. See `references/interview-evidence-extraction.md` for the current search playbook.

Use Gmail searches around the company name, contact person name, contact email, and obvious permutations.
Use calendar searches around the company name and contact names.
Use the jobs table to find the process record, job title, job description, and any job link.

If interview dates are now an array, inspect every date separately and map each one to its own calendar evidence before proposing any update. When the process has multiple meetings, build a local review table first with all matched timestamps, titles, and calendar URLs, then decide whether they belong to one process record.

Important: the job description comes from the jobs table only, never from Calendar.

Support file: `references/interview-calendar-mapping.md`

## Source priority

Use the strongest explicit source first:

1. Jobs table — job title, job description, company row, known status, job link
2. Gmail — process state, recruiter emails, outcomes, next steps, participant names, compact body text
3. Calendar — timing, meeting invitations, organizer names, meeting dates, event URLs
4. User-provided data — overrides guesses when explicit

Important:
- Use the job description from the Jobs table only.
- Do not use the calendar text as the job description.
- Calendar can inform timing and participants, but not the canonical job description.

When sources conflict, prefer the newest explicit evidence and note the conflict in comments.

## Validation step

Before writing updates, prepare a compact proposed update and ask the user to confirm the parameters if anything is ambiguous or inferred.

Validation should cover:
- company_name
- job_title
- interview_status / status
- contacts_json (names, emails, telegram handles)
- which sources were used

If the data is explicit and unambiguous, you may proceed without asking. If the data is partially inferred, present the proposed values and get user approval before updating.

## Field rules

### company_name
- Prefer the exact company name from Gmail, calendar invite, or jobs table.
- If uncertain, leave blank rather than inventing a name.
- Allowed value: any compact company name string.

### job_title
- Must be a sensible role title.
- Do not store generic calendar event titles like:
  - "15 Min Meeting between Bradley Kearsley and Aleksandr Zalesov"
  - "Intro call with Aleksandr"
- Prefer the actual role name from the jobs table or the email thread.
- If the only source is a generic meeting title, derive the role from Gmail or the jobs table; otherwise leave job_title blank.
- Allowed value: any compact role title string, or blank.

### status / interview_status
- Update based on the latest real evidence from Gmail/Calendar.
- Use the process state, not the meeting platform.
- Standardized capitalized values:
  - Contacted
  - Scheduled
  - Interviewing
  - Awaiting Feedback
  - Rejected
  - Offer
  - Withdrawn
  - No Show
- Use these exact spellings/case for both status and interview_status whenever possible.

### contacts_json
- JSON array of contact objects. Each object may contain any of these fields:
  - `name` — full name
  - `email` — work email address
  - `telegram` — Telegram handle with `@` prefix
  - `facebook` — Facebook profile URL or handle
  - `linkedin` — LinkedIn profile URL
  - any other freeform key (e.g. `phone`, `whatsapp`, `note`)
- Only external people. Never include the user's own email.
- Do not include booking-service or transcript-service addresses:
  - cal.com, calendly.com, hubspot bots
  - Google Calendar notification addresses
  - Tactiq, Fireflies.ai, Otter.ai
  - Zoom / Google Meet / Teams system mailboxes
- Keep recruiters, hiring managers, and interviewers only.
- Each person = one object. Multiple contacts = multiple objects in the array.
- Allowed value: JSON array, e.g.:
  ```json
  [
    {"name": "Katy Peichert", "email": "katy@front.com", "linkedin": "https://linkedin.com/in/katy"},
    {"name": "John Smith", "telegram": "@johnsmith"}
  ]
  ```

### contact_via
- Legacy field — still present in DB but no longer the primary contacts store.
- May still be written for backward compat. Common values: LinkedIn, Email, Telegram, Y-Combinator.
- Prefer putting channel info into the relevant contact object in `contacts_json` instead.

### emails_json
- Store compact relevant email evidence only.
- Do not dump full email history.
- Do not include long footers, legal disclaimers, privacy blocks, repeated quote chains, or tracking junk.
- Keep a compact record per useful email:
  - message id
  - thread id
  - from
  - to
  - subject
  - date
  - a short relevant excerpt
  - a short summary of the meaning
- If multiple emails matter, store multiple compact entries.
- Allowed value: JSON array of compact evidence objects.

### comments
- Use for concise provenance and interpretation.
- Include why the process status changed.
- Mention the source of the update when useful.
- Allowed value: freeform notes, kept short.
- Comments must be simple bullet points only.
- No HTML tags.
- No angle-bracket markup.
- No long URLs.
- Do not paste raw email footers, tracking blobs, or long quoted chains.
- Prefer one short bullet per fact or source.

## Cleaning rules

- Never add the user's email to contacts.
- Never use booking-service or transcript-service email addresses as contacts.
- Never use generic meeting titles as the job title.
- Prefer compact, meaningful titles and roles.
- If the process has no explicit evidence for a field, leave it blank.
- Keep status/contact values normalized and capitalized.

## Suggested interview record shape

- company_name
- job_id
- job_url
- job_title
- status
- interview_status
- interview_dates_json — `[{date, label?, url?}]` — canonical multi-meeting array
- contacts_json — `[{name?, email?, telegram?, linkedin?, facebook?, ...}]`
- description
- comments
- emails_json
- contact_via (legacy, still writable for compat)

## Multiple interview dates

- When one process has more than one meeting, store all matched calendar times in `interview_dates_json` as an array.
- Each array item: `{date: "YYYY-MM-DDTHH:MM", label?: "Technical round", url?: "https://calendar.google.com/..."}`
- Do not flatten a multi-meeting process into a single timestamp; the array is the canonical record.
- A local mapping table is useful while reconciling calendar matches before writing updates.

## Dashboard editing behavior

- The comments field should be a multiline textarea in the dashboard.
- Default comments height: 2 rows.
- Cmd+Enter, Ctrl+Enter, and Shift+Enter insert a newline inside comments; plain Enter commits the edit.
- Meeting time entries are add/remove only; the time itself does not need inline editing.
- Keep meeting time display compact: show the time as the link text, but do not render the raw calendar domain beside it.
- When adding a meeting manually, allow an optional calendar event URL to be stored alongside the timestamp.

## Update behavior

- If Gmail says the candidate is not a fit, mark the process rejected.
- If Gmail says next step / interview scheduled, reflect that.
- If Gmail or Calendar only provides a generic meeting title, reconstruct the real role from the surrounding evidence.
- Keep the record compact and readable.

## Good examples

```json
{
  "company_name": "Front",
  "job_title": "Senior Applied AI Engineer",
  "interview_status": "rejected",
  "contacts_json": [
    {"name": "Katy Peichert", "email": "katarzyna.peichert@front.com"}
  ]
}
```

```json
{
  "company_name": "Inception",
  "job_title": "Senior Product Engineer",
  "contacts_json": [
    {"name": "Darya Samsonova", "email": "darya@missionhire.tech", "telegram": "@darya"},
    {"name": "Sergey Guk", "email": "sg@inception.one"}
  ],
  "interview_dates_json": [
    {"date": "2026-06-10T14:00", "label": "Intro call"},
    {"date": "2026-06-17T11:00", "label": "Technical round"}
  ]
}
```

## Bad examples

- `job_title`: "15 Min Meeting between Bradley Kearsley and Aleksandr Zalesov"
- contacts_json entry: `{"email": "zallesov@gmail.com"}` — user's own email
- contacts_json entry: `{"email": "hello@cal.com"}` — booking service
- contacts_json entry: `{"email": "transcripts@tactiq.io"}` — transcript service
- contact_via: "Zoom" — meeting platform, not contact channel
