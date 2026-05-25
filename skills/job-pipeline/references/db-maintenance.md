# Database Maintenance

## Deleting Jobs

**User preference: hard DELETE, not soft-delete.** When the user explicitly says "delete", use SQL DELETE FROM not UPDATE SET status='deleted'. Soft-delete was tried once and the user immediately corrected: "please delete them for real. not status=delete. use SQL DELETE."

```sql
-- Hard delete all jobs from a provider
DELETE FROM jobs WHERE provider = '<name>';

-- Hard delete a range of IDs
DELETE FROM jobs WHERE id BETWEEN 2081 AND 2100;

-- Check what you're about to delete first
SELECT COUNT(*), MIN(id), MAX(id) FROM jobs WHERE provider = '<name>';
```

**The HARD RULE still applies:** Never delete without an explicit, unambiguously affirmative user command. The user will say "delete" when they mean it. Never suggest or propose deletion.

## Bulk Delete Pattern

When the user says "delete all X jobs":
1. Count + confirm to the user what will be deleted
2. Hard-delete with DELETE FROM
3. Verify with SELECT COUNT(*)

Note: All provider jobs (greenhouse, wellfound, sprout, jobleads, hirify) have been hard-deleted at various points during setup. After deletion, re-running the pipeline will re-scrape from scratch.
