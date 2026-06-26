# JobLand field mapping (Wellfound enrich → JobLandMCP)

Canonical mapping from an `enriched.json` job row to JobLand record fields. Used by the
enrich write step (and by apply/screen). Write **only via JobLandMCP** (`jobs_create` /
`jobs_update`). Field names below are the JobLand schema names; if the MCP tool exposes
different names, use the names the MCP schema accepts and keep this intent.

## Mapping

| enriched.json        | JobLand field          | Notes |
|----------------------|------------------------|-------|
| `title`              | `title`                | required |
| `company`            | `posted_company_name`  | required; also forms `dedup_key = "{company}::{title}"` |
| `url`                | `url`                  | required; the Wellfound `/jobs/<id>` URL |
| `apply_url`          | `apply_url`            | external ATS link **or** the Wellfound URL for in-app apply (see below) |
| `description`        | `description`          | plain text, HTML stripped |
| `compensation`       | `salary_raw`           | raw string, e.g. `"$80k – $140k • No equity"` |
| `locations` (array)  | `location`             | join with `, ` (e.g. `"Berlin, Remote"`) |
| `remote`             | `remote_scope`         | `true → "remote"`, else from location text |
| `posted`             | `date_posted`          | as shown (e.g. "Posted 2 weeks ago") if no exact date |
| —                    | `source`               | always `"wellfound"` |
| —                    | `status`               | set to `"enriched"` on create |

Country: derive from `locations` when obvious (e.g. "Berlin" → DE); otherwise leave unset.

## Required vs optional

- **Required to create**: `title`, `posted_company_name`, `url`, `source`.
- Skip a row entirely if `enriched: false` (do not write half-empty records).
- Everything else is optional — write what is present, omit nulls.

## In-app apply (no external apply URL)

The enrich script already sets, per the user's rule:
- `apply_url` = the **Wellfound job URL** when there is no external ATS link
- `apply_type` = `"in_app"` (vs `"external"`)

So `apply_url` is always populated. Persist `apply_type` if the schema has a field for it;
otherwise it is informational only. Do not block writing on a missing external link.

## What NOT to overwrite on update

If `jobs_find_by_url` finds an existing record, update **only enrich-owned fields**
(title, company, description, salary_raw, location, remote_scope, apply_url, date_posted).
**Never overwrite** user/pipeline-owned fields:
- `user_status` (applied / rejected / offer / withdrawn)
- screening/assessment fields (`apply_verdict`, scores, `research_*`)
- `status` if already past `enriched` (e.g. `screened`)

When in doubt, only fill fields that are currently empty.
