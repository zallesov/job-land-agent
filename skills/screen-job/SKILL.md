# screen-job

Screen a job against the candidate's profile and produce a lightweight assessment.

## Input

`Use skill screen-job. job_id: 42. cv_path: /path/to/cv.md`

## Task

1. Read the CV from cv_path
2. Read the job from the database using job_id (use your DB read tools). Fields: title, description, company name, location, remote_scope, salary_range.
3. Assess the job against the candidate's profile. Evaluate ALL of the following:
   - **apply_verdict**: one of "Strong Apply" | "Apply with Caution" | "Need Research" | "Skip"
     - "Strong Apply": clear match — right seniority, tech stack, remote, no red flags
     - "Apply with Caution": worth applying but notable caveats (borderline tech fit, unclear remote, no salary info)
     - "Need Research": potentially interesting but cannot assess without more context (no description, vague company, unclear remote policy)
     - "Skip": hard disqualifiers — on-site only, junior/entry-level, completely unrelated domain, requires relocation outside target list (Berlin, Spain, EU remote)
   - **relevance_score**: 0–100 based on tech stack fit, seniority match, remote eligibility, domain relevance
   - **one_line_summary**: one sentence describing the role and fit
   - **seniority_fit**: brief note on level match
   - **tech_stack_fit**: brief note on tech overlap with candidate's profile
   - **remote_eligibility**: what the job says about remote; candidate target is EU remote / Berlin / Spain
   - **salary_assessment**: posted salary or "Not disclosed" if absent

## Output

Respond with a single JSON block. No prose.

```json
{
  "status": "success",
  "apply_verdict": "Strong Apply",
  "relevance_score": 85,
  "one_line_summary": "Senior backend Python role, fully remote EU, great stack fit",
  "seniority_fit": "Senior IC, matches target level",
  "tech_stack_fit": "Python, Postgres, Kafka — strong overlap",
  "remote_eligibility": "Fully remote, EU timezone",
  "salary_assessment": "€90k–120k posted"
}
```

Failure (cannot read job or CV):
```json
{"status": "failure", "error": "could not load job description"}
```

## Rules
- apply_verdict is always one of the four exact strings above
- relevance_score must be an integer 0–100
- Do NOT research the company — assess only from the job description and CV
- If description is missing or too short to assess, use verdict "Need Research"
