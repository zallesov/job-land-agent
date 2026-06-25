---
name: apply-job
description: Use when interactively applying to a tracked JobLand job while never submitting the final application.
---

# Apply Job

## Trigger

Use when the user says `apply for job #N`, `apply to <company>`, `apply job_id=N`, or similar.

## Hard Rules

- Use JobLandMCP for JobLand job records. Do not use local scripts, SQL, direct backend clients, or storage-specific knowledge.
- Never click Submit, Apply, Send, or any submit-equivalent final button.
- The browser must be visible. The user reviews and submits manually.
- Ask application-content questions one at a time and wait for answers.

## Phase 1: Read Job

1. Extract `job_id`.
2. Read the job with `jobs_get`.
3. Capture from the MCP response: id, title, company name, apply URL, source URL, description, existing verdict/summary if present.
4. If the job is missing, stop and ask the user to verify the id.

Use local profile files only for candidate-owned material such as CV/config if they are part of the active profile. Do not use them for JobLand record access.

## Phase 2: Open Application Form

Open the job's apply URL in the visible authenticated browser. If `apply_url` is missing, use the source URL from the MCP record.

If the page requires login, stop and let the user log in manually.

## Phase 3: Inspect Form

Read the form structure from the visible browser:
- text inputs: name, email, phone, location, LinkedIn, GitHub, salary, years of experience
- textareas: cover letter, work experience, essay questions
- dropdowns: authorization, relocation, pronouns, source
- file inputs: resume/CV upload
- checkboxes: consent/GDPR/newsletter
- video/voice requirements

Do not fill diversity/EEOC fields unless the user explicitly asks.

## Phase 4: Video or Voice Requirement

If the form requires video or voice:
1. Extract the exact prompt.
2. Give the user a concise speech outline.
3. Ask whether to proceed or skip.
4. If the user skips, leave the JobLand record unchanged and stop.

## Phase 5: Application Text

For essay/screening forms:
- Draft one concise answer per question based on the CV and job description.
- Respect visible character limits.
- Present answers for user edits before filling.

For cover-letter forms, ask these one at a time:
1. Why does this role at the company interest you?
2. Any recent achievement or project not on the CV that is relevant?
3. Anything specific the hiring team should know?

Then draft up to three short cover letter options and let the user choose or edit.

## Phase 6: Fill Form

Fill simple fields and approved text in the visible browser. Keep the browser open for user review.

Report:
- fields filled
- fields not filled
- video/voice requirement, if any
- explicit reminder that Submit was not clicked

## Phase 7: Mark Applied

Only after the user confirms they submitted manually, update the JobLand record through `jobs_update` with the appropriate applied/user status field exposed by MCP.

If the MCP response does not expose an applied/status field, do not guess. State that marking applied requires a JobLandMCP-supported status field.
