---
name: screen-job
description: Use to screen enriched jobs against the candidate CV + preferences and write the apply verdict onto the job record via JobLandMCP (status -> screened). Provider-agnostic; runs on a subagent with a cheap model.
---

# Screen Job

Assess one or more **enriched** jobs against the candidate's CV and preferences, then write
the verdict **onto the job record itself** (1:1) and advance its `status` to `screened`.

- **DB access is JobLandMCP only** (`jobs_get`, `jobs_list`, `jobs_update`). Never use a
  local DB client, SQL, or a screening script.
- Designed to run on a **subagent with a cheap model** — it is a short, rubric-driven
  judgement over text already in the DB. No browser, no web research.
- The verdict lives on the job (fields below), not in a separate collection.

## Inputs

One of:
- **A specific job id** — screen exactly that job.
- **A batch** — select the worklist yourself via
  `jobs_list { origin: "<provider>", status: "enriched" }` (e.g. `origin: "wellfound"`).
  Screen each returned job, one by one, writing each result as you go.

## Context to load once

- **CV:** `config/cv.md`.
- **Preferences** from `config/user.yaml`: `job_preferences`, `languages`, `desired_salary`.
  If any are empty, ignore that constraint.

## Per job

1. `jobs_get { id }` (or use the row from the batch list). Read: `title`,
   `posted_company_name`, `location`, `remote_scope`, `salary_range`, `description`.
2. Judge with the rubric below — **only from the job text + CV. Do not research the company.**
3. `jobs_update { id, fields: { ...verdict fields..., status: "screened" } }` (see "Write back").

## Rubric

Pick exactly one `apply_verdict`:

- **"Strong Apply"** — clear match: right seniority, tech stack, remote-eligible, no red
  flags, aligns with preferences.
- **"Apply with Caution"** — worth applying but notable caveats (borderline tech fit,
  unclear remote, no salary info).
- **"Need Research"** — potentially interesting but cannot assess without more context
  (no/short description, vague company, unclear remote policy). **Use this if the
  description is missing or too short to assess.**
- **"Skip"** — hard disqualifiers: on-site only, junior/entry-level, unrelated domain,
  relocation outside Berlin / Spain / EU-remote, **or** explicitly conflicts with
  `job_preferences` (e.g. a stack the user said to avoid), **or** requires a language the
  candidate does not speak.

Scoring / constraints:
- `relevance_score` = integer 0–100 (tech-stack fit, seniority match, remote eligibility,
  domain relevance).
- `job_preferences` and `languages` are **hard constraints** for "Skip": if the job clearly
  violates them, the verdict is "Skip" regardless of tech fit.
- `desired_salary`: if the posted salary is clearly below target, downgrade to "Skip" or
  "Apply with Caution" by severity. If salary is undisclosed, do not penalise on salary alone.

## Write back (A1 — verdict on the job)

On a successful judgement, `jobs_update` the job with:

| field | value |
|-------|-------|
| `apply_verdict` | one of the four verdicts above |
| `relevance_score` | integer 0–100 |
| `one_line_summary` | one short sentence — the headline reason |
| `screen_summary` | 1–3 sentences of rationale (optional but preferred) |
| `seniority_fit` | short phrase |
| `tech_stack_fit` | short phrase |
| `remote_eligibility` | short phrase |
| `salary_assessment` | short phrase |
| `status` | `"screened"` |

**Never overwrite** user/pipeline-owned fields: `user_status`, `apply_url`, `description`,
`title`, `posted_company_name` — only write the verdict fields + `status`.

## On failure (do nothing — stay resumable)

If you genuinely cannot screen a job (tool error, no usable content even for "Need
Research"), **leave it at `status: "enriched"` and do not write a verdict.** Per the
pipeline state machine, a job only advances on success — the next run will re-select it.
Do **not** invent a verdict to force progress. Surface the problem instead.

## Done criterion

Every job you took from `status = enriched` is either now `status = screened` with a
verdict written, or untouched (left at `enriched`) because it could not be assessed. No job
is screened twice — `screened` jobs are never re-selected by `status = enriched`.
