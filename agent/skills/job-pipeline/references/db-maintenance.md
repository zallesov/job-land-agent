# Database Maintenance

**DB is PocketBase, not SQLite.** No SQL access — use `scripts/pb_client.py` (`PBClient.get_list` / `.delete`). The client has no bulk-delete or table-wipe method by design — only single-record delete by id. This is intentional: it makes mass deletion require an explicit loop you write and run, never a one-liner.

## Deleting Jobs

**User preference: hard DELETE, not soft-status.** When the user explicitly says "delete", remove the record (`pb.delete("jobs", record_id)`), not `status='deleted'`. Soft-delete was tried once and the user immediately corrected: "please delete them for real. not status=delete."

```python
from scripts.pb_client import get_pb
pb = get_pb()

# Check what you're about to delete FIRST
matches = pb.get_list("jobs", "provider='<name>'", per_page=500)
print(len(matches), [m["id"] for m in matches][:5])

# Only after explicit user confirmation:
for job in matches:
    pb.delete("jobs", job["id"])
```

**The HARD RULE still applies:** Never delete without an explicit, unambiguously affirmative user command. The user will say "delete" when they mean it. Never suggest or propose deletion. Never write or run a delete loop against the default `POCKETBASE_URL` (production) without the user having confirmed the exact count/filter first.

## Bulk Delete Pattern

When the user says "delete all X jobs":
1. `get_list` + count + show the user what will be deleted (ids, sample)
2. Wait for explicit confirmation
3. Hard-delete record by record via `pb.delete()`
4. Verify with another `get_list` (should be empty)

Note: All provider jobs (greenhouse, wellfound, sprout, jobleads, hirify) have been hard-deleted at various points during setup. After deletion, re-running the pipeline will re-scrape from scratch.
