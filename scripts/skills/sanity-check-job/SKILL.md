# sanity-check-job

Quickly filter a job against the candidate's profile before deep research.

## Input

`Use skill sanity-check-job. job_id: 42. cv_path: /path/to/cv.md`

## Task

1. Read the CV from cv_path
2. Read the job from the database using the job_id (use your DB read tools)
3. Check ONLY these hard disqualifiers:
   - Requires physical on-site presence (not remote-eligible)
   - Requires relocation to a location not in the candidate's target list (Berlin, Spain, or EU remote)
   - Junior/entry-level role (candidate is senior/principal level)
   - Completely unrelated domain (e.g. hardware, medical, legal)
4. If none apply: verdict = "pass"
5. If any apply: verdict = "skip" with the specific reason

## Output

Respond with a single JSON block. No prose.

Pass:
```json
{"status": "success", "verdict": "pass", "reason": "Remote senior backend role, matches profile"}
```

Skip:
```json
{"status": "success", "verdict": "skip", "reason": "On-site only, Berlin office required"}
```

Failure (cannot read job or CV):
```json
{"status": "failure", "error": "could not load job description"}
```

## Rules
- verdict is always "pass" or "skip" when status="success"
- Do NOT apply subjective judgements — only hard disqualifiers listed above
- A job with "hybrid" or unclear remote policy should pass (not skip)
