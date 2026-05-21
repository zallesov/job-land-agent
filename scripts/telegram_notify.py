#!/usr/bin/env python3
"""
Send Telegram notifications via hermes send.

Usage:
  python3 telegram_notify.py --type daily_digest --db jobs.db --run-id 5
  python3 telegram_notify.py --type research_complete --job-id 12 --db jobs.db
  python3 telegram_notify.py --type pipeline_failure --provider greenhouse --step scrape --error "timeout" --artifact-path outputs/greenhouse/runs/
  python3 telegram_notify.py --type research_failed --job-id 12 --db jobs.db --error "LLM returned invalid JSON"
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from db import get_connection

HERMES = "/Users/zall/.local/bin/hermes"
TELEGRAM_TARGET = "telegram"


def _send(message: str) -> None:
    result = subprocess.run(
        [HERMES, "send", "--to", TELEGRAM_TARGET, message],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"Telegram send failed: {result.stderr}", file=sys.stderr)


def daily_digest(db_path: str, run_id: int) -> None:
    con = get_connection(db_path)
    run = con.execute("SELECT * FROM pipeline_runs WHERE id = ?", (run_id,)).fetchone()
    if not run:
        _send("Daily jobs run: pipeline_run not found")
        return

    summary: dict = {}
    if run["summary_json"]:
        try:
            summary = json.loads(run["summary_json"])
        except Exception:
            pass

    inserted = summary.get("inserted", 0)
    failed = summary.get("failed", 0)
    status_emoji = "✅" if run["status"] == "succeeded" else ("⚠️" if run["status"] == "partial" else "❌")

    lines = [
        f"{status_emoji} Daily jobs run: {run['status']}",
        f"New jobs: {inserted}",
    ]

    if inserted == 0 and failed == 0:
        providers = con.execute(
            "SELECT DISTINCT provider FROM jobs "
            "WHERE first_seen >= datetime('now', '-25 hours')"
        ).fetchall()
        # Fall back to showing run_type from recent pipeline_runs
        recent_runs = con.execute(
            "SELECT run_type FROM pipeline_runs "
            "WHERE started_at >= datetime('now', '-25 hours') AND status = 'succeeded'"
        ).fetchall()
        provider_names = [r["provider"] for r in providers]
        if not provider_names:
            provider_names = [r["run_type"].replace("ingest:", "").split("_jobs_live")[0]
                              for r in recent_runs]
        provider_str = ", ".join(f"{p} OK" for p in provider_names) if provider_names else "all providers OK"
        lines.append(f"Providers: {provider_str}")
    elif inserted > 0:
        new_jobs = con.execute(
            "SELECT j.title, j.posted_company_name, j.country, j.url "
            "FROM jobs j "
            "WHERE j.first_seen >= datetime('now', '-25 hours') "
            "ORDER BY j.first_seen DESC LIMIT 20"
        ).fetchall()
        lines.append("\nNew jobs:")
        for job in new_jobs:
            lines.append(
                f"• {job['title'] or '?'} @ {job['posted_company_name'] or '?'} ({job['country'] or '?'})"
            )

    if failed > 0:
        lines.append(f"\n⚠️ Failed items: {failed}")

    con.close()
    _send("\n".join(lines))


def pipeline_failure(provider: str, step: str, error: str, artifact_path: str) -> None:
    msg = (
        f"❌ Job pipeline failure\n"
        f"Provider/step: {provider} {step}\n"
        f"Error: {error[:200]}\n"
        f"Artifacts/logs: {artifact_path}\n"
        f"Action: fix scraper with Codex before next run"
    )
    _send(msg)


def research_complete(db_path: str, job_id: int) -> None:
    con = get_connection(db_path)
    job = con.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    assessment = con.execute(
        "SELECT * FROM job_assessments WHERE job_id = ?", (job_id,)
    ).fetchone()
    research = con.execute(
        "SELECT cr.trustworthiness_score FROM company_research cr "
        "JOIN jobs j ON j.company_id = cr.company_id WHERE j.id = ?", (job_id,)
    ).fetchone()
    con.close()

    if not job or not assessment:
        _send(f"Research complete for job {job_id} (no details available)")
        return

    trust = research["trustworthiness_score"] if research else "?"
    msg = (
        f"🔬 Research complete\n"
        f"{job['title'] or '?'} - {job['posted_company_name'] or '?'}\n"
        f"Verdict: {assessment['apply_verdict'] or '?'}\n"
        f"Relevance: {assessment['relevance_score'] or '?'}\n"
        f"Trust: {trust}\n"
        f"Summary: {assessment['one_line_summary'] or '?'}\n"
        f"Source: {job['apply_url'] or job['url']}\n"
        f"Dashboard: http://localhost:3000"
    )
    _send(msg)


def research_failed(db_path: str, job_id: int, error: str) -> None:
    con = get_connection(db_path)
    job = con.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    con.close()
    title = job["title"] if job else f"job {job_id}"
    company = job["posted_company_name"] if job else "?"
    msg = (
        f"❌ Research failed\n"
        f"{title} - {company}\n"
        f"Error: {error[:200]}\n"
        f"Dashboard: http://localhost:3000\n"
        f"Action: inspect command error and rerun from dashboard"
    )
    _send(msg)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--type", required=True,
                        choices=["daily_digest", "pipeline_failure", "research_complete", "research_failed"])
    parser.add_argument("--db")
    parser.add_argument("--run-id", type=int)
    parser.add_argument("--job-id", type=int)
    parser.add_argument("--provider")
    parser.add_argument("--step")
    parser.add_argument("--error")
    parser.add_argument("--artifact-path")
    args = parser.parse_args()

    if args.type == "daily_digest":
        daily_digest(args.db, args.run_id)
    elif args.type == "pipeline_failure":
        pipeline_failure(args.provider or "?", args.step or "?",
                         args.error or "unknown", args.artifact_path or "?")
    elif args.type == "research_complete":
        research_complete(args.db, args.job_id)
    elif args.type == "research_failed":
        research_failed(args.db, args.job_id, args.error or "unknown")


if __name__ == "__main__":
    main()
