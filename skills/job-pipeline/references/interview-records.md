# Interview record management

This reference captures the stable conventions for the interview table used in the local job DB/dashboard.

## Source priority

1. Gmail
   - Best source for recruiter emails, follow-ups, rejection/feedback, and exact contact details.
   - Prefer explicit sender/recipient information and message body over calendar text.
2. Calendar
   - Best source for timing, meeting title, and invite attendees.
   - Use to create the record and to fill `next_interview_date`.
3. Job DB
   - Use for `job_id`, `job_title`, `company_name`, and job link when a match exists.
4. LinkedIn / Telegram / YCombinator
   - Use only when the outreach origin is explicit in the message/thread or profile metadata.

## Field rules

- `company_name`: prefer the company named in the recruiter email thread or invite sender domain.
- `job_id`: only set when there is a real DB match; do not guess.
- `job_title`: use the job title from the DB when linked; otherwise the event/interview title.
- `contact_via`: this means the outreach channel, not the meeting platform. Allowed values: `email`, `LinkedIn`, `telegram`, `Ycombinator`.
- `contacts`: only external people. Never add the user's own email address.
- `comments`: store the evidence trail and short reasoning.
- `emails_json`: store matched Gmail messages with at least `gmail_message_id`, `threadId`, `from`, `to`, `subject`, `date`, `snippet`, `body`, `matched_query`.
- `description`: short summary of what the interview is about or the invite text.
- `status` / `interview_status`: reflect the actual process state, not the calendar state.

## Status lifecycle

Suggested values:
- `contacted`
- `scheduled`
- `completed`
- `awaiting feedback`
- `rejected`
- `offer`
- `no show`
- `withdrawn`

Rules:
- Use `awaiting feedback` only when the latest evidence indicates the company is still reviewing you after the interview.
- If a recruiter says you are not the best fit / not moving forward, use `rejected`.
- If no interview has happened yet, keep the row in an early state such as `contacted` or `scheduled`.

## Gmail search strategy

Try, in order:
1. exact company name
2. recruiter/contact person name
3. contact email
4. exact interview title
5. company domain if present

Prefer the first thread that contains an explicit invite, update, or outcome email. If a search returns a noisy newsletter or unrelated thread, keep searching.

## Record update pattern

When updating a row:
1. Pull the best Gmail message(s)
2. Extract the exact evidence
3. Update `company_name`, `contacts`, `contact_via`, `interview_status`, and `comments`
4. Store the matched Gmail payload in `emails_json`
5. Update `job_id` only if there is a clear job match

## Pitfalls

- Do not confuse calendar platform names with outreach channels.
- Do not use the calendar event as proof of outcome.
- Do not add the user's own email to contact lists.
- Do not over-normalize company names when the email thread already gives the correct name.
- If an invite is from a scheduling system, inspect the originating recruiter email/thread before deciding the company.
