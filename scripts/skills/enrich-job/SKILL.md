# enrich-job

Enrich a job listing by visiting its URL and extracting structured data.

## Input

You will receive a prompt like:
`Use skill enrich-job. job_id: 42. url: https://boards.greenhouse.io/company/jobs/123. cv_path: /path/to/cv.md`

## Task

1. Open the URL using your browser tools
2. Extract the following fields from the job page:
   - title (job title, exact)
   - description (full job description, max 2000 chars)
   - apply_url (the direct application URL, if different from listing URL)
   - salary_range (salary range as shown, e.g. "90-120K EUR"; null if not shown)
   - date_posted (ISO date YYYY-MM-DD if available; null otherwise)

## Output

Respond with a single JSON block. No prose before or after.

Success:
```json
{"status": "success", "title": "Senior Backend Engineer", "description": "...", "apply_url": "https://...", "salary_range": "90-120K EUR", "date_posted": "2026-05-10"}
```

Failure (login wall, 404, extraction error):
```json
{"status": "failure", "error": "login wall"}
```

## Rules
- If the page requires login, return failure with error="login wall"
- If the page returns 404/not found, return failure with error="page not found"
- If you can't extract meaningful description (< 100 chars), return failure with error="extraction failed"
- apply_url defaults to the input url if no separate apply link is found
- Do NOT include CV content in the output
