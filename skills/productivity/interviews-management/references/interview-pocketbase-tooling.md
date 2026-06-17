# Interview PocketBase tooling

Use this reference when reconciling interview rows in the PocketBase-backed dashboard from Gmail + Calendar evidence.

## Why this exists

This profile already has `scripts/pb_client.py` plus one-off PocketBase writers for jobs/research, but interview updates were still being done ad hoc via inline Node/`fetch` snippets. That is workable for one session, but too fragile for repeated dry-runs and selective writes.

## Recommended tooling to add under `scripts/`

### 1. `db_read_interviews.py`
Purpose:
- list interview rows from PocketBase
- fetch one row by id
- filter by company name substring
- print normalized JSON for agent review

Suggested flags:
- `--id <record_id>`
- `--company <name>`
- `--recent <N>`
- `--json`

### 2. `db_write_interview.py`
Purpose:
- update one interview row from stdin JSON
- create a new interview row with `--create`
- normalize `status` / `interview_status`
- auto-stamp `updated_at`
- read back the record after write and print verification JSON

Suggested behavior:
- accept `--id <record_id>` for updates
- accept stdin payload only for mutable interview fields
- reject unknown top-level keys loudly

### 3. `interview_dry_run_recent.py`
Purpose:
- fetch recent calendar events for a time window
- fetch matching Gmail evidence
- fetch existing PocketBase interview rows
- emit a structured write-set without mutating PocketBase

Suggested output buckets:
- `add`
- `update`
- `tentative_add`
- `ignore`

### 4. `interview_apply_write_set.py`
Purpose:
- read an approved dry-run JSON write-set
- apply only selected rows
- verify each create/update by reading back from PocketBase
- print compact old -> new summary

## Normalization rules to centralize in code

Keep these in a shared helper instead of re-deriving them in every session:
- `status`: `applied | in_process | rejected | offer`
- `interview_status`: `scheduled | awaiting_response`
- comments stored as short bullet lines only
- dedupe `contacts_json` by `(name,email,telegram,linkedin)`
- dedupe `interview_dates_json` by `(date,url,label)`

## Evidence tie-breakers worth encoding

These came up in live use and should be in tooling, not just in the agent prompt:
- a newly scheduled interview can override a stale `rejected` row for the same company/process
- a declined calendar invite is not automatically a hiring rejection
- generic calendar titles like `Interviews (Alexander Zalesov)` or `15 Minute Meeting` are still valid if organizer email / surrounding Gmail thread ties them to a real company
- LinkedIn application/rejection notification templates are valid process evidence even without direct recruiter mail
- later rounds should extend `interview_dates_json`, not create duplicate rows

## Safe write sequence

1. Run dry-run script for the target time window.
2. Review proposed `add/update/tentative_add/ignore` buckets.
3. Get explicit user approval before any PocketBase mutation.
4. Apply approved subset only.
5. Read back touched rows and show persisted values.

## Why this matters

Without dedicated scripts, the agent falls back to inline Node/heredoc writes against PocketBase. Those are harder to audit, harder to reuse, and easy to get wrong when many interview rows change at once.
