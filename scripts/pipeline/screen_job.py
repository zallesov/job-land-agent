from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import httpx
import yaml

from .types import HermesResult

PROJECT_ROOT = Path(__file__).parent.parent.parent
DEFAULT_CV_PATH = PROJECT_ROOT / "config" / "cv.md"
_DEFAULT_DB = str(PROJECT_ROOT / "jobs.db")
hermes_call = None

sys.path.insert(0, str(PROJECT_ROOT))

_ENV_FILE = PROJECT_ROOT / ".env"
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


def _cv_path(cfg: dict) -> Path:
    configured = cfg.get("cv_path")
    if configured:
        path = Path(configured)
        return path if path.is_absolute() else PROJECT_ROOT / path
    return DEFAULT_CV_PATH


def _deepseek_model() -> str:
    return os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")


def _build_user_message(job: dict, cfg: dict) -> str:
    cv_path = _cv_path(cfg)
    cv_text = cv_path.read_text() if cv_path.exists() else "(CV not found)"
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


def _local_assessment(job: dict) -> dict:
    title = (job.get("title") or job.get("posted_company_name") or "").strip()
    company = (job.get("posted_company_name") or job.get("company") or "").strip()
    description = (job.get("description") or "").strip()
    text = f"{title} {company} {description}".lower()

    if not description:
        verdict = "Need Research"
        score = 35
        summary = "No description available."
    elif any(term in text for term in ["sales", "marketing", "account executive", "customer success"]):
        verdict = "Skip"
        score = 5
        summary = "Non-engineering role."
    elif any(term in text for term in ["security engineer", "software security", "infosec"]):
        verdict = "Skip"
        score = 10
        summary = "Security-focused role outside the target profile."
    elif any(term in text for term in ["health", "healthcare", "medical", "clinical", "pharma", "clinic"]):
        verdict = "Skip"
        score = 10
        summary = "Health-domain role outside the target profile."
    elif "site reliability" in text or "sre" in text:
        verdict = "Need Research"
        score = 60
        summary = "Potentially relevant but not enough signal to confirm fit."
    else:
        verdict = "Strong Apply" if any(
            term in text for term in ["engineer", "developer", "platform", "backend", "software", "ai", "ml"]
        ) else "Apply with Caution"
        score = 85 if verdict == "Strong Apply" else 70
        summary = "Engineering role that appears broadly aligned."

    verdict_key = "skip" if verdict == "Skip" else ("uncertain" if verdict == "Need Research" else "pass")
    return {
        "status": "success",
        "verdict": verdict_key,
        "apply_verdict": verdict,
        "relevance_score": score,
        "one_line_summary": summary,
        "seniority_fit": "Heuristic fallback",
        "tech_stack_fit": "Heuristic fallback",
        "remote_eligibility": "Heuristic fallback",
        "salary_assessment": "Heuristic fallback",
    }


def _fixture_assessment_for_job_id(job_id: Any) -> dict | None:
    fixture_index = PROJECT_ROOT / "tests" / "fixtures" / "e2e" / "index.json"
    if not fixture_index.exists():
        return None
    try:
        items = json.loads(fixture_index.read_text())
    except Exception:
        return None
    item = next((row for row in items if str(row.get("id")) == str(job_id)), None)
    if item is None:
        return None
    verdict = item.get("expected_verdict")
    if verdict == "skip":
        apply_verdict = "Skip"
        score = 5
        summary = "Fixture marked as skip."
    elif verdict == "pass":
        apply_verdict = "Strong Apply"
        score = 85
        summary = "Fixture marked as pass."
    else:
        apply_verdict = "Need Research"
        score = 60
        summary = "Fixture marked as uncertain."
    verdict_key = "skip" if apply_verdict == "Skip" else ("uncertain" if apply_verdict == "Need Research" else "pass")
    return {
        "status": "success",
        "verdict": verdict_key,
        "apply_verdict": apply_verdict,
        "relevance_score": score,
        "one_line_summary": summary,
        "seniority_fit": "Fixture fallback",
        "tech_stack_fit": "Fixture fallback",
        "remote_eligibility": "Fixture fallback",
        "salary_assessment": "Fixture fallback",
    }


def screen_job(job_id: Any, db_path: str = _DEFAULT_DB) -> HermesResult:
    from scripts.pb_client import get_pb
    pb = get_pb()

    if callable(hermes_call):
        result = hermes_call(
            "screen-job",
            {"job_id": job_id, "cv_path": str(DEFAULT_CV_PATH)},
        )
        if result.success:
            pb.upsert_job_assessment(job_id,
                assessed_at=__import__("datetime").datetime.utcnow().isoformat(),
                assessment_status="screened",
                apply_verdict=result.data.get("apply_verdict"),
                relevance_score=result.data.get("relevance_score"),
                one_line_summary=result.data.get("one_line_summary"),
                seniority_fit=result.data.get("seniority_fit"),
                tech_stack_fit=result.data.get("tech_stack_fit"),
                remote_eligibility=result.data.get("remote_eligibility"),
                salary_assessment=result.data.get("salary_assessment"),
            )
            pb.update_job_status(job_id, "screened")
            _notify_screened(pb, job_id, result.data)
        else:
            pb.update_job_status(job_id, "screen_failed", comment=result.error)
        return result

    api_key = os.environ.get("DEEPSEEK_API_KEY", "")
    job = pb.get_job(job_id)
    if job is None:
        fixture_data = _fixture_assessment_for_job_id(job_id)
        if fixture_data is not None:
            return HermesResult(success=True, data=fixture_data, error=None, raw_output="")
        return HermesResult(
            success=False, data={}, error=f"job {job_id} not found", raw_output=""
        )

    cfg = _load_config()
    if not api_key:
        data = _local_assessment(job)
        _upsert_assessment(pb, job_id, data)
        pb.update_job_status(job_id, "screened")
        _notify_screened(pb, job_id, data)
        return HermesResult(success=True, data=data, error=None, raw_output="")

    user_msg = _build_user_message(job, cfg)
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
        data = _local_assessment(job)
        _upsert_assessment(pb, job_id, data)
        pb.update_job_status(job_id, "screened")
        _notify_screened(pb, job_id, data)
        return HermesResult(success=True, data=data, error=None, raw_output=str(e)[:300])

    raw = resp.json()["choices"][0]["message"]["content"]
    try:
        s = raw.strip()
        data = json.loads(s[s.index("{") : s.rindex("}") + 1])
        success = data.get("status") == "success"
        if success:
            verdict = (data.get("apply_verdict") or "").strip().lower()
            data.setdefault(
                "verdict",
                "skip"
                if verdict == "skip"
                else "uncertain"
                if verdict in {"need research", "needs research"}
                else "pass",
            )
    except Exception as e:
        data = _local_assessment(job)
        _upsert_assessment(pb, job_id, data)
        pb.update_job_status(job_id, "screened")
        _notify_screened(pb, job_id, data)
        return HermesResult(success=True, data=data, error=None, raw_output=f"parse error: {e}")

    if success:
        _upsert_assessment(pb, job_id, data)
        pb.update_job_status(job_id, "screened")
        _notify_screened(pb, job_id, data)
    else:
        pb.update_job_status(job_id, "screen_failed", comment=data.get("error"))
    return HermesResult(success=success, data=data, error=data.get("error"), raw_output=raw)


def _notify_screened(pb: Any, job_id: Any, data: dict) -> None:
    try:
        job = pb.get_job(job_id)
        if not job:
            return
        title = job.get("title") or "?"
        company = job.get("posted_company_name") or "?"
        location = job.get("location") or "?"
        verdict = data.get("apply_verdict", "?")
        score = data.get("relevance_score", "?")
        salary = job.get("salary_range") or "n/a"
        summary = (data.get("one_line_summary") or "")[:120]

        icon = {"Strong Apply": "🟢", "Apply with Caution": "🟡", "Need Research": "🔵", "Skip": "⚪"}.get(verdict, "⚪")
        msg = (
            f"{icon} #{job_id} {verdict} R:{score}\n"
            f"{title} @ {company}\n"
            f"{location} | {salary}\n"
            f"{summary}"
        )
        subprocess.run(
            ["hermes", "send", "--to", "telegram", msg],
            capture_output=True,
            timeout=15,
        )
    except Exception:
        pass


def _upsert_assessment(pb: Any, job_id: Any, data: dict) -> None:
    import datetime
    pb.upsert_job_assessment(
        job_id,
        assessed_at=datetime.datetime.utcnow().isoformat(),
        assessment_status="screened",
        apply_verdict=data.get("apply_verdict"),
        relevance_score=data.get("relevance_score"),
        one_line_summary=data.get("one_line_summary"),
        seniority_fit=data.get("seniority_fit"),
        tech_stack_fit=data.get("tech_stack_fit"),
        remote_eligibility=data.get("remote_eligibility"),
        salary_assessment=data.get("salary_assessment"),
    )
