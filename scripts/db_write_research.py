#!/usr/bin/env python3
"""
Write research JSON (from stdin) to PocketBase.

Usage:
  echo '<json>' | python3 db_write_research.py --job-id 123
  python3 db_write_research.py --job-id 123 --command-id 456 < result.json

--db is accepted but ignored (PocketBase config comes from .env).
"""
import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from scripts.pb_client import get_pb


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", help="(ignored — PocketBase is used)")
    parser.add_argument("--job-id", required=True, dest="job_id")
    parser.add_argument("--command-id", dest="command_id")
    args = parser.parse_args()

    try:
        result = json.load(sys.stdin)
    except json.JSONDecodeError as e:
        print(f"ERROR: invalid JSON on stdin: {e}", file=sys.stderr)
        return 1

    pb = get_pb()
    job = pb.get_job(args.job_id)
    if not job:
        print(f"ERROR: job {args.job_id} not found", file=sys.stderr)
        if args.command_id:
            pb.complete_command(args.command_id, "failed", error=f"job {args.job_id} not found")
        return 1

    import datetime
    now_iso = datetime.datetime.utcnow().isoformat()

    company_id = job.get("company_id") or ""
    if company_id:
        written = pb.upsert_company_research(
            company_id,
            researched_at=now_iso,
            research_status="researched",
            legitimacy_check=result.get("legitimacy_check") or "",
            hiring_entity_type=result.get("hiring_entity_type") or "",
            founded_year=result.get("founded_year"),
            hq_location=result.get("hq_location") or "",
            employee_count=result.get("employee_count") or "",
            headcount_trend=result.get("headcount_trend") or "",
            funding_summary=result.get("funding_summary") or "",
            funding_stage=result.get("funding_stage") or "",
            risk_news=result.get("risk_news") or "",
            glassdoor_summary=result.get("glassdoor_summary") or "",
            clutch_summary=result.get("clutch_summary") or "",
            trustworthiness_score=result.get("trustworthiness_score"),
            research_notes=result.get("research_notes") or "",
            source_urls_json=json.dumps(result.get("source_urls", [])),
            raw_research_json=json.dumps(result),
        )
        if written is None:
            print(f"Reusing existing company research for company_id={company_id}", file=sys.stderr)
    else:
        print(f"WARN: job {args.job_id} has no company_id — skipping company_research insert", file=sys.stderr)

    pb.upsert_job_assessment(
        args.job_id,
        assessed_at=now_iso,
        assessment_status="researched",
        relevance_score=result.get("relevance_score"),
        apply_verdict=result.get("apply_verdict") or "",
        one_line_summary=result.get("one_line_summary") or "",
        red_flag_scan=result.get("red_flag_scan") or "",
        seniority_fit=result.get("seniority_fit") or "",
        tech_stack_fit=result.get("tech_stack_fit") or "",
        salary_assessment=result.get("salary_assessment") or "",
        remote_eligibility=result.get("remote_eligibility") or "",
    )

    job_updates: dict = {"research_status": "researched"}
    salary_range = result.get("salary_range")
    if salary_range and salary_range != "Not found" and not job.get("salary_range"):
        job_updates["salary_range"] = salary_range
    apply_url = result.get("apply_url")
    if apply_url and apply_url != "Not found":
        job_updates["apply_url"] = apply_url
    pb.update_job(args.job_id, **job_updates)

    pb.log_event(
        "job", args.job_id, "research_complete", "hermes_research",
        json.dumps({"verdict": result.get("apply_verdict"), "score": result.get("relevance_score")}),
    )

    result_json = json.dumps({
        "verdict": result.get("apply_verdict"),
        "relevance_score": result.get("relevance_score"),
        "trustworthiness_score": result.get("trustworthiness_score"),
        "one_line_summary": result.get("one_line_summary"),
    })

    if args.command_id:
        pb.complete_command(args.command_id, "succeeded", result_json=result_json)

    pb.complete_pending_scrape_commands(args.job_id, result_json)

    summary = (
        f"Written: {result.get('apply_verdict')} "
        f"R:{result.get('relevance_score')} T:{result.get('trustworthiness_score')}"
    )
    print(summary)
    _notify_telegram(args.job_id, result)
    return 0


def _notify_telegram(job_id: str, result: dict) -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_HOME_CHANNEL")
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
