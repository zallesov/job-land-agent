#!/usr/bin/env python3
"""
Write research JSON (from stdin) to SQLite DB.

Usage:
  echo '<json>' | python3 db_write_research.py --db jobs.db --job-id 123
  python3 db_write_research.py --db jobs.db --job-id 123 --command-id 456 < result.json
"""
import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from db import get_connection, log_event


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", required=True)
    parser.add_argument("--job-id", type=int, required=True)
    parser.add_argument("--command-id", type=int)
    args = parser.parse_args()

    try:
        result = json.load(sys.stdin)
    except json.JSONDecodeError as e:
        print(f"ERROR: invalid JSON on stdin: {e}", file=sys.stderr)
        return 1

    con = get_connection(args.db)
    job = con.execute("SELECT * FROM jobs WHERE id=?", (args.job_id,)).fetchone()
    if not job:
        print(f"ERROR: job {args.job_id} not found", file=sys.stderr)
        if args.command_id:
            con.execute(
                "UPDATE agent_commands SET status='failed', finished_at=datetime('now'), error=? WHERE id=?",
                (f"job {args.job_id} not found", args.command_id),
            )
            con.commit()
        con.close()
        return 1

    company_id = job["company_id"]
    if company_id:
        existing = con.execute(
            "SELECT id FROM company_research WHERE company_id=?", (company_id,)
        ).fetchone()
        if not existing:
            con.execute(
                """INSERT INTO company_research (
                    company_id, researched_at, research_status,
                    legitimacy_check, hiring_entity_type, founded_year,
                    hq_location, employee_count, headcount_trend,
                    funding_summary, funding_stage, risk_news,
                    glassdoor_summary, clutch_summary, trustworthiness_score,
                    research_notes, source_urls_json, raw_research_json
                ) VALUES (?,datetime('now'),'researched',?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    company_id,
                    result.get("legitimacy_check"), result.get("hiring_entity_type"),
                    result.get("founded_year"), result.get("hq_location"),
                    result.get("employee_count"), result.get("headcount_trend"),
                    result.get("funding_summary"), result.get("funding_stage"),
                    result.get("risk_news"), result.get("glassdoor_summary"),
                    result.get("clutch_summary"),
                    result.get("trustworthiness_score"), result.get("research_notes"),
                    json.dumps(result.get("source_urls", [])), json.dumps(result),
                ),
            )
        else:
            print(f"Reusing existing company research for company_id={company_id}", file=sys.stderr)

    existing_assessment = con.execute(
        "SELECT id FROM job_assessments WHERE job_id=?", (args.job_id,)
    ).fetchone()
    params = (
        result.get("relevance_score"), result.get("apply_verdict"),
        result.get("one_line_summary"), result.get("red_flag_scan"),
        result.get("seniority_fit"), result.get("tech_stack_fit"),
        result.get("ic_or_management"), result.get("salary_assessment"),
        result.get("remote_eligibility"), result.get("visa_contract_structure"),
        result.get("ai_native_assessment"), result.get("assessment_notes"),
        json.dumps(result.get("source_urls", [])), json.dumps(result),
    )
    if existing_assessment:
        con.execute(
            """UPDATE job_assessments SET
                assessed_at=datetime('now'), assessment_status='researched',
                relevance_score=?, apply_verdict=?, one_line_summary=?,
                red_flag_scan=?, seniority_fit=?, tech_stack_fit=?,
                ic_or_management=?, salary_assessment=?, remote_eligibility=?,
                visa_contract_structure=?, ai_native_assessment=?,
                assessment_notes=?, source_urls_json=?, raw_assessment_json=?,
                updated_at=datetime('now')
            WHERE job_id=?""",
            params + (args.job_id,),
        )
    else:
        con.execute(
            """INSERT INTO job_assessments (
                job_id, assessed_at, assessment_status,
                relevance_score, apply_verdict, one_line_summary,
                red_flag_scan, seniority_fit, tech_stack_fit,
                ic_or_management, salary_assessment, remote_eligibility,
                visa_contract_structure, ai_native_assessment,
                assessment_notes, source_urls_json, raw_assessment_json
            ) VALUES (?,datetime('now'),'researched',?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (args.job_id,) + params,
        )

    salary_range = result.get("salary_range")
    if salary_range and salary_range != "Not found":
        con.execute(
            "UPDATE jobs SET salary_range=?, updated_at=datetime('now') WHERE id=? AND (salary_range IS NULL OR salary_range='')",
            (salary_range, args.job_id),
        )

    apply_url = result.get("apply_url")
    if apply_url and apply_url != "Not found":
        con.execute(
            "UPDATE jobs SET apply_url=?, updated_at=datetime('now') WHERE id=?",
            (apply_url, args.job_id),
        )

    con.execute(
        "UPDATE jobs SET status='researched', updated_at=datetime('now') WHERE id=?",
        (args.job_id,),
    )
    log_event(
        con, "job", args.job_id, "research_complete", "hermes_research",
        json.dumps({"verdict": result.get("apply_verdict"), "score": result.get("relevance_score")}),
    )

    result_json = json.dumps({
        "verdict": result.get("apply_verdict"),
        "relevance_score": result.get("relevance_score"),
        "trustworthiness_score": result.get("trustworthiness_score"),
        "one_line_summary": result.get("one_line_summary"),
    })

    if args.command_id:
        con.execute(
            """UPDATE agent_commands SET status='succeeded', finished_at=datetime('now'),
               result_json=? WHERE id=?""",
            (result_json, args.command_id),
        )

    # also close any pending/running scrape_job command for this job
    con.execute(
        """UPDATE agent_commands SET status='succeeded', finished_at=datetime('now'),
           result_json=?
           WHERE command_type='scrape_job'
             AND status IN ('pending','running')
             AND json_extract(payload_json,'$.job_id')=?""",
        (result_json, args.job_id),
    )

    con.commit()
    con.close()

    summary = (
        f"Written: {result.get('apply_verdict')} "
        f"R:{result.get('relevance_score')} T:{result.get('trustworthiness_score')}"
    )
    print(summary)
    _notify_telegram(args.job_id, result)
    return 0


def _notify_telegram(job_id: int, result: dict) -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_HOME_CHANNEL")
    if not token or not chat_id:
        env_file = Path(__file__).parent.parent / ".hermes" / "profiles" / "interviewprep" / ".env"
        if not env_file.exists():
            env_file = Path.home() / ".hermes" / "profiles" / "interviewprep" / ".env"
        if env_file.exists():
            for line in env_file.read_text().splitlines():
                line = line.strip()
                if line.startswith("TELEGRAM_BOT_TOKEN=") and not line.startswith("#"):
                    token = line.split("=", 1)[1].strip()
                elif line.startswith("TELEGRAM_HOME_CHANNEL=") and not line.startswith("#"):
                    chat_id = line.split("=", 1)[1].strip()
    if not token or not chat_id:
        print("WARN: TELEGRAM_BOT_TOKEN/TELEGRAM_HOME_CHANNEL not set, skipping notify", file=sys.stderr)
        return
    try:
        import urllib.request
        verdict = result.get("apply_verdict", "?")
        r_score = result.get("relevance_score", "?")
        t_score = result.get("trustworthiness_score", "?")
        summary = result.get("one_line_summary", "")
        text = f"Research done: job #{job_id}\nVerdict: {verdict} | R:{r_score} T:{t_score}\n{summary}"
        payload = json.dumps({"chat_id": chat_id, "text": text}).encode()
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        urllib.request.urlopen(req, timeout=10)
        print("Telegram notified", file=sys.stderr)
    except Exception as e:
        print(f"WARN: Telegram notify failed: {e}", file=sys.stderr)


if __name__ == "__main__":
    raise SystemExit(main())
