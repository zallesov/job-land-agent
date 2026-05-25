from __future__ import annotations

import json
import os
from pathlib import Path

import httpx
import yaml

from .types import HermesResult
from scripts.db import get_connection, update_job_status

PROJECT_ROOT = Path(__file__).parent.parent.parent
CV_PATH = PROJECT_ROOT / "cv_master_content.md"
_DEFAULT_DB = str(PROJECT_ROOT / "jobs.db")

# Load .env from hermes-profile if present
_ENV_FILE = PROJECT_ROOT / "hermes-profile" / ".env"
if _ENV_FILE.exists():
    for _line in _ENV_FILE.read_text().splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _, _v = _line.partition("=")
            os.environ.setdefault(_k.strip(), _v.strip())

_SYSTEM_PROMPT = """\
You are a job screening assistant. Assess job postings against a candidate's CV.

Verdicts (pick exactly one):
- "Strong Apply": clear match — right seniority, tech stack, remote, no red flags, aligns with preferences
- "Apply with Caution": worth applying but notable caveats (borderline tech fit, unclear remote, no salary info)
- "Need Research": potentially interesting but cannot assess without more context (no description, vague company, unclear remote policy)
- "Skip": hard disqualifiers — on-site only, junior/entry-level, completely unrelated domain, requires relocation outside Berlin/Spain/EU remote, OR explicitly conflicts with job_preferences (e.g. fintech role when user said "no fintech"), OR requires a language the candidate doesn't speak

Rules:
- relevance_score is an integer 0–100 based on tech stack fit, seniority match, remote eligibility, domain relevance
- Do NOT research the company — assess only from the job description and CV
- If description is missing or too short to assess, use verdict "Need Research"
- job_preferences and languages are hard constraints for "Skip" — if the job clearly violates them, verdict is "Skip" regardless of tech fit
- desired_salary: if posted salary is clearly below target, downgrade verdict to "Skip" or "Apply with Caution" depending on severity
- If job_preferences, languages, or desired_salary are empty, ignore them

Respond with ONLY a single JSON object, no markdown fences, no surrounding text:
{"status":"success","apply_verdict":"...","relevance_score":0,"one_line_summary":"...","seniority_fit":"...","tech_stack_fit":"...","remote_eligibility":"...","salary_assessment":"..."}

On failure: {"status":"failure","error":"reason"}\
"""


def _load_config() -> dict:
    path = PROJECT_ROOT / "config" / "user.yaml"
    if path.exists():
        return yaml.safe_load(path.read_text()) or {}
    return {}


def _deepseek_model() -> str:
    return os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")


def _build_user_message(job: dict, cfg: dict) -> str:
    cv_text = CV_PATH.read_text() if CV_PATH.exists() else "(CV not found)"
    prefs = cfg.get("job_preferences") or "not specified"
    langs = cfg.get("languages") or "not specified"
    salary = cfg.get("desired_salary") or "not specified"

    return f"""\
## Candidate CV
{cv_text}

## Candidate preferences
- Job preferences: {prefs}
- Languages: {langs}
- Desired salary: {salary}

## Job to assess
Title: {job.get('title') or '(unknown)'}
Company: {job.get('posted_company_name') or job.get('company') or '(unknown)'}
Location: {job.get('location') or '(unknown)'}
Remote scope: {job.get('remote_scope') or '(unknown)'}
Salary: {job.get('salary_range') or 'Not disclosed'}

Description:
{(job.get('description') or '').strip() or '(no description)'}
"""


def screen_job(job_id: int, db_path: str = _DEFAULT_DB) -> HermesResult:
    api_key = os.environ.get("DEEPSEEK_API_KEY", "")
    if not api_key:
        return HermesResult(
            success=False, data={}, error="DEEPSEEK_API_KEY not set", raw_output=""
        )

    con = get_connection(db_path)
    try:
        job = con.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        if job is None:
            return HermesResult(
                success=False, data={}, error=f"job {job_id} not found", raw_output=""
            )

        cfg = _load_config()
        user_msg = _build_user_message(dict(job), cfg)
        model = _deepseek_model()

        try:
            resp = httpx.post(
                "https://api.deepseek.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": _SYSTEM_PROMPT},
                        {"role": "user", "content": user_msg},
                    ],
                    "temperature": 0.1,
                    "max_tokens": 512,
                },
                timeout=60.0,
            )
            resp.raise_for_status()
        except Exception as e:
            err = str(e)[:300]
            update_job_status(con, job_id, "screen_failed", comment=err)
            con.commit()
            return HermesResult(success=False, data={}, error=err, raw_output="")

        raw = resp.json()["choices"][0]["message"]["content"]
        try:
            s = raw.strip()
            data = json.loads(s[s.index("{") : s.rindex("}") + 1])
            success = data.get("status") == "success"
        except Exception as e:
            err = f"parse error: {e}"
            update_job_status(con, job_id, "screen_failed", comment=err)
            con.commit()
            return HermesResult(success=False, data={}, error=err, raw_output=raw)

        if success:
            _upsert_assessment(con, job_id, data)
            update_job_status(con, job_id, "screened")
        else:
            update_job_status(con, job_id, "screen_failed", comment=data.get("error"))
        con.commit()
        return HermesResult(success=success, data=data, error=data.get("error"), raw_output=raw)
    finally:
        con.close()


def _upsert_assessment(con, job_id: int, data: dict) -> None:
    existing = con.execute(
        "SELECT id FROM job_assessments WHERE job_id = ?", (job_id,)
    ).fetchone()
    fields = (
        data.get("apply_verdict"),
        data.get("relevance_score"),
        data.get("one_line_summary"),
        data.get("seniority_fit"),
        data.get("tech_stack_fit"),
        data.get("remote_eligibility"),
        data.get("salary_assessment"),
    )
    if existing:
        con.execute("""
            UPDATE job_assessments SET
                assessed_at = datetime('now'),
                assessment_status = 'screened',
                apply_verdict = ?, relevance_score = ?,
                one_line_summary = ?, seniority_fit = ?,
                tech_stack_fit = ?, remote_eligibility = ?,
                salary_assessment = ?,
                updated_at = datetime('now')
            WHERE job_id = ?
        """, fields + (job_id,))
    else:
        con.execute("""
            INSERT INTO job_assessments (
                job_id, assessed_at, assessment_status,
                apply_verdict, relevance_score, one_line_summary,
                seniority_fit, tech_stack_fit, remote_eligibility, salary_assessment
            ) VALUES (?, datetime('now'), 'screened', ?, ?, ?, ?, ?, ?, ?)
        """, (job_id,) + fields)
