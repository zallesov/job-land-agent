# PocketBase-only job pipeline notes

Use this as the default mental model for the job pipeline after the SQLite migration.

## Core rule
- Do not thread `db_path` through job pipeline code.
- Do not read or write job data through `scripts.db`.
- Use `scripts.pb_client.get_pb()` for all job, assessment, company, command, and run records.

## Common patterns
- Dedup: `pb.get_dedup_keys([...])` and `pb.get_existing_urls([...])`
- Read job: `pb.get_job(job_id)`
- Read by URL: `pb.get_job_by_url(url)`
- Write job: `pb.insert_job(...)`, `pb.update_job(...)`, `pb.update_job_status(...)`
- Assessments: `pb.upsert_job_assessment(job_id, ...)`
- Research: `pb.upsert_company_research(company_id, ...)`
- Runs: `pb.create_pipeline_run(...)`, `pb.finish_pipeline_run(...)`

## Migration checklist
When converting a legacy helper:
1. Remove `--db jobs.db` from CLI entry points.
2. Remove `db_path` from helper signatures.
3. Replace SQL reads with PB helpers plus Python-side filtering.
4. Replace SQL joins with explicit PB lookups (`job` → `assessment` → `company_research`).
5. Re-run a repo-wide search for `jobs.db`, `sqlite3`, `from scripts.db`, and `db_path` in job-related files.

## Common gotchas
- `get_list()` returns a list, not `items`; filter results in Python if you need joins or length checks.
- PocketBase filters are not SQL; keep them simple and move anything complex (date windows, lengths, joins) into Python.
- Some old code still carries legacy `db_path` arguments even after it is PB-backed; remove the plumbing, not just the SQL.

## Related skills
- `enrich-job` for Chrome/CDP extraction and enrich recovery.
- `screen-job` for assessment and verdict writes.
- `add-job-by-url` for a single-job pipeline run.
- `check-auth` for provider session validation.
