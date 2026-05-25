---
name: add-job-by-url
description: Add a single job by URL. Runs the same dedup → ingest → enrich → screen pipeline as the automated scraper. Triggered when user provides a job posting URL.
---

# Add Job by URL

## Trigger

Any message containing a job posting URL (e.g. `https://boards.greenhouse.io/...`, `https://wellfound.com/jobs/...`, any `https://` URL that looks like a job posting).

Also triggered by: "add this job", "track this job", "add job by url".

## Execution

Run immediately, no confirmation needed:

```bash
python3 scripts/add_job_by_url.py --url <url>
```

The script handles everything: dedup → ingest → enrich (CDP) → screen (Hermes) → Telegram notification.

Output includes job title, company, verdict, relevance score, and one-line summary.

## Duplicate

If output contains `DUPLICATE:` — report "Already tracked" and stop.

## Failures

- `ENRICH_FAILED:` — enrich failed (job in DB with `enrich_failed`); report error
- `SCREEN_FAILED:` — screen failed (job in DB); report error

## CRITICAL: Visible Chrome

The enrichment step opens a new CDP page. `page.bring_to_front()` MUST be called so the user can watch. See the `job-pipeline` skill's `references/chrome-visibility.md`.

## Chrome pre-flight

```bash
curl -s http://localhost:9222/json/version | grep -q "{" && echo "OK" || echo "NOT_RUNNING"
```

If `NOT_RUNNING`: tell user to run `bash start-chrome.sh` first.
