---
name: assess-jobs-due-diligence
description: Use when researching and scoring jobs in jobs_all.xlsx for legitimacy, company trustworthiness, reputation, red flags, role fit, and apply/skip verdicts, then writing assessment fields back to the spreadsheet without overwriting user comments or interview statuses.
---

# Assess Jobs Due Diligence

## Overview

Use this skill to research jobs in `/Users/zall/interviews/jobs_all.xlsx` and write due-diligence assessment fields back into the same workbook. Always preserve user-maintained workflow fields such as `status`, `comment`, and `current interview status`.

## Non-Negotiables

- Use the job `url` as the row key.
- Do not delete rows.
- Do not overwrite `status`, `comment`, or `current interview status`.
- Cite a source URL for every non-obvious claim.
- If information cannot be found, write `Not found`; do not guess or infer.
- Prefer primary sources: company website, original job posting, official LinkedIn company page, official Crunchbase/company funding page, Glassdoor, credible news.
- Use web search for current information and include source URLs in `assessment source urls`.

## Workflow

1. Read target rows from `jobs_all.xlsx`. If the user does not specify rows, process rows whose `assessment status` is blank, or process a small batch and report how many remain.
2. For each job, research:
   - original job posting
   - company website
   - LinkedIn company profile
   - Glassdoor or similar reviews
   - Crunchbase or funding profile where available
   - news search for the last 18 months
3. Fill the assessment JSON array, one object per job URL.
4. Write the assessment JSON to an intermediate file, for example:

   ```text
   /Users/zall/interviews/outputs/assessments/job_assessments_YYYY-MM-DD.json
   ```

5. Apply it to the workbook:

   ```bash
   python3 /Users/zall/interviews/.codex/skills/assess-jobs-due-diligence/scripts/apply_job_assessments.py \
     --xlsx /Users/zall/interviews/jobs_all.xlsx \
     --assessments-json /Users/zall/interviews/outputs/assessments/job_assessments_YYYY-MM-DD.json \
     --today YYYY-MM-DD
   ```

6. Verify row counts and updated assessment fields before reporting completion.

## Assessment Columns

The write-back script creates these columns if they do not already exist:

- `assessment date`
- `assessment status`
- `legitimacy check`
- `hiring entity type`
- `hiring entity mismatch`
- `founded year`
- `hq location`
- `remote policy`
- `linkedin employee count`
- `headcount trend`
- `funding summary`
- `funding stage`
- `company risk news`
- `glassdoor summary`
- `red flag scan`
- `seniority fit`
- `tech stack fit`
- `ic or management`
- `salary assessment`
- `remote eligibility`
- `visa contract structure`
- `ai native assessment`
- `one line summary`
- `apply verdict`
- `relevance score`
- `company trustworthiness score`
- `assessment research notes`
- `assessment source urls`

## Research Brief

### A. Legitimacy Check

Answer:

- Does the company have a real, substantive web presence: working website, active LinkedIn with multiple real employees, real product? `Yes`, `Questionable`, or `No`, with reasoning.
- Is it a genuine employer hiring internally, or a recruiting agency, bootcamp/course/accelerator, paid apprenticeship, MLM, staffing/outsourcing body shop, or other intermediary?
- Is the hiring entity the same as the company named in the posting? Flag mismatches.

### B. Company Profile

Collect:

- Founded year.
- HQ location.
- Remote policy.
- LinkedIn employee count and whether headcount is growing, flat, or shrinking over the last 12 months.
- Funding: total raised, most recent round type/date, lead investors. Flag if the last round was more than about 2 years ago.
- Funding stage interpretation: `pre-seed`, `seed`, `Series A`, `Series B`, `Series C+`, `bootstrapped`, or `public`.
- News of layoffs, restructuring, leadership departures, lawsuits, or financial distress in the last 18 months.

### C. Reputation

Collect:

- Glassdoor rating and number of reviews.
- Recurring positive and negative review themes, especially management, work-life balance, layoffs, pay, and engineering culture.
- CEO approval rating if available.
- Note if reviews are too few to rely on or if there is a suspicious cluster of 5-star reviews.

### D. Red-Flag Scan

Check each:

- Job posting age and reposting evidence.
- Vague or buzzword-heavy description with no concrete responsibilities.
- No salary range or only `competitive`.
- Any request to pay money, buy equipment upfront, or invest.
- Unrealistic claims with no funding/revenue evidence.
- Generic contact details, free email domains, or no named hiring contact.
- Mismatch between company size and role scope/seniority.
- Evidence the company is always hiring this position.

### E. Role Assessment

Assess:

- Seniority level and fit for a Principal/Senior IC with about 20 years of AI/cloud/full-stack experience.
- Tech stack overlap with AI, cloud, full-stack, backend, architecture, platform, and engineering leadership strengths.
- IC vs management.
- Salary vs market for role and location if salary is stated.
- Remote eligibility for Spain/Germany and timezone requirements; flag region locks.
- Visa/contract structure: employment vs contractor and country entity if stated.
- AI-native vs AI-skeptical: whether the company actually builds with AI or merely lists it.

### F. Verdict

Write:

- One-line summary.
- `Apply`, `Apply with caution`, or `Skip`.
- Single most important reason.
- `relevance score` from 0 to 100.
- `company trustworthiness score` from 0 to 100.
- Research notes and source URLs.

## Scoring Rubric

### Relevance Score

Use this 100-point rubric:

- 25: seniority match for Principal/Senior IC or high-impact staff-level work.
- 20: AI/cloud/full-stack/platform architecture overlap.
- 15: remote eligibility from Spain/Germany and timezone fit.
- 15: role type preference fit: strong IC/technical leadership, not pure people management unless explicitly desired.
- 10: compensation signal or likely senior-market compensation.
- 10: product/engineering complexity and opportunity for leverage.
- 5: application practicality, including clear hiring entity and accessible application path.

### Company Trustworthiness Score

Use this 100-point rubric:

- 20: legitimate web presence and real product.
- 15: hiring entity clarity and direct employer relationship.
- 15: employee base and LinkedIn substance.
- 15: funding/revenue/public-company credibility, with early-stage startups allowed to score well if real investors/product/team exist.
- 10: reputation/reviews and engineering culture signal.
- 10: absence of recent distress signals.
- 10: job posting quality and realistic role scope.
- 5: transparent compensation, location, and contract terms.

Examples:

- N26-like regulated, known employer with real product and hiring entity clarity: near 100 if no current severe risk.
- Real early-stage startup with credible founders, seed/Series A backing, substantive product, and clear role: can score 70-90.
- Unknown crypto DEX, offshore shell, anonymous team, no funding/revenue proof, vague role: near 0-25.
- Solopreneur idea-stage company with no funding and no team: low unless the user explicitly wants that risk.

## Assessment JSON Shape

Use this shape for each row:

```json
[
  {
    "url": "https://example.com/job",
    "assessment date": "2026-05-18",
    "assessment status": "researched",
    "legitimacy check": "Yes — working product site and active LinkedIn with 200+ employees. Sources: ...",
    "hiring entity type": "Direct employer",
    "hiring entity mismatch": "No mismatch found",
    "founded year": "2019 — Source: ...",
    "hq location": "Berlin, Germany — Source: ...",
    "remote policy": "Remote within Europe — Source: ...",
    "linkedin employee count": "Not found",
    "headcount trend": "Not found",
    "funding summary": "Series A, date, lead investor. Source: ...",
    "funding stage": "Series A",
    "company risk news": "No layoffs/restructuring found in last 18 months. Search sources: ...",
    "glassdoor summary": "4.1/5 from 80 reviews; themes... Source: ...",
    "red flag scan": "No salary range; posting appears 6 weeks old; no payment requests found. Sources: ...",
    "seniority fit": "Strong fit for senior IC/platform architecture...",
    "tech stack fit": "Strong AI/cloud/backend overlap...",
    "ic or management": "IC",
    "salary assessment": "Not found",
    "remote eligibility": "Eligible for Spain/Germany timezone — Source: ...",
    "visa contract structure": "Not found",
    "ai native assessment": "AI-native product; sources...",
    "one line summary": "Credible AI infrastructure role with strong senior IC fit.",
    "apply verdict": "Apply",
    "relevance score": "86",
    "company trustworthiness score": "78",
    "assessment research notes": "Concise narrative with citations inline.",
    "assessment source urls": "https://company.example; https://linkedin.com/company/...; https://..."
  }
]
```

## Verification Commands

After applying assessments:

```bash
python3 -c 'import importlib.util, json; p="/Users/zall/interviews/.codex/skills/consolidate-jobs-workbook/scripts/consolidate_jobs_workbook.py"; s=importlib.util.spec_from_file_location("u", p); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); rows=m.read_xlsx(m.Path("/Users/zall/interviews/jobs_all.xlsx")); print(json.dumps({"rows": len(rows), "researched": sum(1 for r in rows if r.get("assessment status")), "with_verdict": sum(1 for r in rows if r.get("apply verdict")), "with_relevance_score": sum(1 for r in rows if r.get("relevance score")), "with_trustworthiness_score": sum(1 for r in rows if r.get("company trustworthiness score")), "with_sources": sum(1 for r in rows if r.get("assessment source urls")), "with_comment": sum(1 for r in rows if r.get("comment")), "with_current_interview_status": sum(1 for r in rows if r.get("current interview status"))}, indent=2))'
```
