# Dry-run reconciliation heuristics

Use this when reviewing recent calendar + Gmail activity before writing interview-table changes.

## Strong add signal

Create a new interview-process proposal when all of these are true:
- there is a real calendar interview/invite in the target window
- Gmail contains either a recruiter/interviewer message, an interview confirmation, or an explicit outcome
- no existing interview row matches the company/process

Typical examples:
- calendar interview + later rejection email → propose a new rejected row with compact evidence
- calendar interview + confirmation email + no existing row → propose a new in-process row

## Strong update signals

### New scheduled round overrides stale rejected state
If an existing row is marked `rejected` but a newer recruiter/interviewer email or calendar invite clearly schedules another round for the same company/process, treat the row as stale and propose moving it back to an active state.

Preferred dry-run note:
- `new interview scheduled after stale rejected state; propose status=in_process`

### Multi-round process must accumulate dates
If one process already exists and later rounds appear in calendar, append them to `interview_dates_json` instead of creating a second row.
Keep one process row per company/role unless evidence clearly shows a different role.

### Calendar-decline is not a process rejection
A `Declined:` invite email or an organizer decline only proves that a meeting changed or was cancelled.
Do not mark the process rejected from invite-decline alone unless Gmail also contains an explicit hiring outcome.

## Ignore / low-signal calendar items

Do not propose interview rows for:
- self-booked placeholder events
- generic personal planning blocks
- events that name no company/process and have no supporting Gmail evidence

Low-confidence rows may still be shown in dry-run output, but label them explicitly as tentative.

## Dry-run output shape

When many interviews changed at once, group proposals as:
- `add`
- `update`
- `tentative_add`
- `ignore`

For each proposal, show:
- company/process
- why it matched
- strongest Gmail evidence
- strongest calendar evidence
- old -> new fields only
