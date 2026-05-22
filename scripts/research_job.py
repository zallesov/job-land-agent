#!/usr/bin/env python3
"""
Research a single job: company due diligence + job assessment via Claude API.

Usage:
  python3 research_job.py --db jobs.db --job-id 123
  python3 research_job.py --db jobs.db --job-id 123 --command-id 456
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from db import get_connection, log_event

try:
    import anthropic
except ImportError:
    print("ERROR: anthropic package not installed. Run: pip3 install anthropic", file=sys.stderr)
    sys.exit(1)

MODEL = "claude-sonnet-4-6"
DB_PATH_DEFAULT = str(Path(__file__).parent.parent / "jobs.db")

RESEARCH_SYSTEM = """You are a job opportunity researcher. Given a job posting, you:
1. Assess the posting company's legitimacy, type (direct employer vs recruiter/agency), and trustworthiness.
2. Research company profile: founding year, HQ, employee count, funding, news, Glassdoor reputation.
3. Assess job fit: seniority, tech stack, remote eligibility, salary, visa/contract structure, AI-nativeness.
4. Produce a one-line verdict and relevance score (0-100) and trust score (0-100).

You MUST respond with valid JSON matching the schema exactly. Use "Not found" for missing fields, never omit keys.
Cite source URLs in source_urls. Do not infer hidden clients for recruiter posts."""

SCHEMA_DESCRIPTION = """{
  "legitimacy_check": "string",
  "hiring_entity_type": "direct | recruiter | agency | intermediary | unknown",
  "founded_year": integer_or_null,
  "hq_location": "string",
  "employee_count": "string",
  "headcount_trend": "string",
  "funding_summary": "string",
  "funding_stage": "string",
  "risk_news": "string",
  "glassdoor_summary": "string",
  "trustworthiness_score": integer_0_to_100,
  "relevance_score": integer_0_to_100,
  "apply_verdict": "Strong Apply | Apply with Caution | Skip",
  "one_line_summary": "string",
  "red_flag_scan": "string",
  "seniority_fit": "string",
  "tech_stack_fit": "string",
  "ic_or_management": "IC | Management | Both | Unknown",
  "salary_assessment": "string",
  "remote_eligibility": "string",
  "visa_contract_structure": "string",
  "ai_native_assessment": "string",
  "assessment_notes": "string",
  "research_notes": "string",
  "source_urls": ["url1", "url2"]
}"""


def _update_command(con, command_id: int, status: str,
                    result_json: str | None = None, error: str | None = None) -> None:
    if status == "running":
        con.execute(
            "UPDATE agent_commands SET status='running', started_at=datetime('now') WHERE id=?",
            (command_id,)
        )
    else:
        con.execute(
            "UPDATE agent_commands SET status=?, finished_at=datetime('now'), result_json=?, error=? WHERE id=?",
            (status, result_json, error, command_id)
        )
    con.commit()


def research_job(db_path: str, job_id: int, command_id: int | None = None) -> int:
    con = get_connection(db_path)
    job = con.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    if not job:
        print(f"ERROR: job {job_id} not found", file=sys.stderr)
        if command_id:
            _update_command(con, command_id, "failed", error=f"job {job_id} not found")
        con.close()
        return 1

    if command_id:
        _update_command(con, command_id, "running")

    log_event(con, "job", job_id, "research_started", "research_job")
    con.commit()

    prompt = f"""Research this job posting and respond ONLY with a JSON object matching this schema:
{SCHEMA_DESCRIPTION}

Job details:
Title: {job['title'] or 'Unknown'}
Company: {job['posted_company_name'] or 'Unknown'}
URL: {job['url']}
Apply URL: {job['apply_url'] or job['url']}
Location: {job['location'] or 'Unknown'} ({job['country'] or 'Unknown'})
Remote: {job['remote_scope'] or 'Unknown'}

Description (first 3000 chars):
{(job['description'] or '')[:3000]}
"""

    con.execute(
        "UPDATE jobs SET status='researching', updated_at=datetime('now') WHERE id=?",
        (job_id,)
    )
    con.commit()

    client = anthropic.Anthropic()
    try:
        message = client.messages.create(
            model=MODEL,
            max_tokens=4096,
            system=RESEARCH_SYSTEM,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = message.content[0].text.strip()
        # Strip markdown code blocks if present
        if raw.startswith("```"):
            parts = raw.split("```")
            raw = parts[1] if len(parts) > 1 else raw
            if raw.startswith("json"):
                raw = raw[4:]
        result = json.loads(raw)
    except json.JSONDecodeError as e:
        err = f"LLM returned invalid JSON: {e}"
        log_event(con, "job", job_id, "research_failed", "research_job", json.dumps({"error": err}))
        if command_id:
            _update_command(con, command_id, "failed", error=err)
        con.commit()
        con.close()
        return 1
    except Exception as e:
        err = str(e)
        log_event(con, "job", job_id, "research_failed", "research_job", json.dumps({"error": err}))
        if command_id:
            _update_command(con, command_id, "failed", error=err)
        con.commit()
        con.close()
        return 1

    # Upsert company_research (reuse existing forever unless force-refresh added later)
    company_id = job["company_id"]
    if company_id:
        existing_research = con.execute(
            "SELECT id FROM company_research WHERE company_id = ?", (company_id,)
        ).fetchone()
        if not existing_research:
            con.execute("""
                INSERT INTO company_research (
                    company_id, researched_at, research_status,
                    legitimacy_check, hiring_entity_type, founded_year,
                    hq_location, employee_count, headcount_trend,
                    funding_summary, funding_stage, risk_news,
                    glassdoor_summary, trustworthiness_score,
                    research_notes, source_urls_json, raw_research_json
                ) VALUES (?,datetime('now'),'researched',?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                company_id,
                result.get("legitimacy_check"), result.get("hiring_entity_type"),
                result.get("founded_year"), result.get("hq_location"),
                result.get("employee_count"), result.get("headcount_trend"),
                result.get("funding_summary"), result.get("funding_stage"),
                result.get("risk_news"), result.get("glassdoor_summary"),
                result.get("trustworthiness_score"), result.get("research_notes"),
                json.dumps(result.get("source_urls", [])), json.dumps(result),
            ))
        else:
            print(f"Reusing existing company research for company_id={company_id}", file=sys.stderr)

    # Always upsert job_assessments
    existing_assessment = con.execute(
        "SELECT id FROM job_assessments WHERE job_id = ?", (job_id,)
    ).fetchone()
    assessment_params = (
        result.get("relevance_score"), result.get("apply_verdict"),
        result.get("one_line_summary"), result.get("red_flag_scan"),
        result.get("seniority_fit"), result.get("tech_stack_fit"),
        result.get("salary_assessment"), result.get("remote_eligibility"),
    )
    if existing_assessment:
        con.execute("""
            UPDATE job_assessments SET
                assessed_at=datetime('now'), assessment_status='researched',
                relevance_score=?, apply_verdict=?, one_line_summary=?,
                red_flag_scan=?, seniority_fit=?, tech_stack_fit=?,
                salary_assessment=?, remote_eligibility=?,
                updated_at=datetime('now')
            WHERE job_id=?
        """, assessment_params + (job_id,))
    else:
        con.execute("""
            INSERT INTO job_assessments (
                job_id, assessed_at, assessment_status,
                relevance_score, apply_verdict, one_line_summary,
                red_flag_scan, seniority_fit, tech_stack_fit,
                salary_assessment, remote_eligibility
            ) VALUES (?,datetime('now'),'researched',?,?,?,?,?,?,?,?)
        """, (job_id,) + assessment_params)

    con.execute(
        "UPDATE jobs SET status='researched', updated_at=datetime('now') WHERE id=?",
        (job_id,)
    )
    log_event(con, "job", job_id, "research_complete", "research_job",
              json.dumps({
                  "verdict": result.get("apply_verdict"),
                  "score": result.get("relevance_score"),
              }))
    if command_id:
        _update_command(con, command_id, "succeeded", result_json=json.dumps({
            "verdict": result.get("apply_verdict"),
            "relevance_score": result.get("relevance_score"),
            "trustworthiness_score": result.get("trustworthiness_score"),
            "one_line_summary": result.get("one_line_summary"),
        }))
    con.commit()
    con.close()
    print(
        f"Research complete: {result.get('apply_verdict')} "
        f"R:{result.get('relevance_score')} T:{result.get('trustworthiness_score')}"
    )
    return 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default=DB_PATH_DEFAULT)
    parser.add_argument("--job-id", type=int, required=True)
    parser.add_argument("--command-id", type=int)
    args = parser.parse_args()
    sys.exit(research_job(args.db, args.job_id, args.command_id))


if __name__ == "__main__":
    main()
