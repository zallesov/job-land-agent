# Interview evidence extraction playbook

Use this when updating one interview-process record for a company.

## Search order
1. Gmail
2. Calendar
3. Jobs table
4. User-provided details

## Company-name permutations
Try multiple forms when searching:
- exact company name
- lower/upper/title case
- punctuation-stripped variants
- domain variants (`front`, `front.com`, `frontcareers`, `frontapp.com`)
- recruiter / interviewer names from the thread

## What to trust
- Job title and job description: Jobs table only
- Process outcome / next step: Gmail first
- Timing / attendees / invite organizer: Calendar

## contacts_json format
Each contact is an object with any of: `name`, `email`, `telegram`, `linkedin`, `facebook`, plus any custom key.
Store one object per person. Example:
```json
[{"name": "Alice", "email": "alice@co.com", "linkedin": "https://linkedin.com/in/alice"}]
```

## What to ignore as contacts
- the user's own email (zallesov@gmail.com)
- booking services: Cal.com, Calendly
- transcript / note services: Tactiq, Fireflies, Otter
- meeting system mailboxes: Zoom, Google Meet, Teams

## Email evidence format
Store compact evidence only:
- message id
- thread id
- from
- to
- subject
- date
- short relevant excerpt
- short meaning summary

## Comments
Comments must be short bullet points only. No HTML, no angle brackets, no long URLs.
