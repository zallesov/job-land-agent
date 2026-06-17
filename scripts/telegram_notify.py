#!/usr/bin/env python3
"""
Send Telegram notifications via hermes send.

Usage:
  python3 telegram_notify.py --type daily_digest --run-id 5
  python3 telegram_notify.py --type research_complete --job-id 12
  python3 telegram_notify.py --type pipeline_failure --provider greenhouse --step scrape --error "timeout" --artifact-path outputs/greenhouse/runs/
  python3 telegram_notify.py --type research_failed --job-id 12 --error "LLM returned invalid JSON"
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from scripts.pb_client import get_pb

HERMES = os.environ.get("HERMES_BIN") or shutil.which("hermes") or "hermes"
TELEGRAM_TARGET = "telegram"


def _send(message: str) -> None:
    result = subprocess.run(
        [HERMES, "send", "--to", TELEGRAM_TARGET, message],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"Telegram send failed: {result.stderr}", file=sys.stderr)


def daily_digest(run_id: int) -> None:
    pb = get_pb()
    run = pb.get("pipeline_runs", str(run_id))
    if not run:
        _send("Daily jobs run: pipeline_run not found")
        return

    summary: dict = {}
    if run.get("summary_json"):
        try:
            summary = json.loads(run["summary_json"])
        except Exception:
            pass

    inserted = summary.get("inserted", 0)
    failed = summary.get("failed", 0)
    status_emoji = "✅" if run.get("status") == "succeeded" else ("⚠️" if run.get("status") == "partial" else "❌")

    lines = [
        f"{status_emoji} Daily jobs run: {run.get('status')}",
        f"New jobs: {inserted}",
    ]

    if summary.get("breakdown_by_provider"):
        lines.append(f"Providers: {summary['breakdown_by_provider']}")
    elif run.get("run_type"):
        lines.append(f"Run type: {run['run_type']}")

    if failed > 0:
        lines.append(f"\n⚠️ Failed items: {failed}")

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


def research_complete(job_id: int) -> None:
    pb = get_pb()
    job = pb.get_job(job_id)
    assessment = pb.get_one("job_assessments", f"job_id='{str(job_id).zfill(15)}'")
    research = pb.get_one("company_research", f"company_id='{job.get('company_id')}'") if job and job.get("company_id") else None

    if not job or not assessment:
        _send(f"Research complete for job {job_id} (no details available)")
        return

    trust = research["trustworthiness_score"] if research else "?"
    msg = (
        f"🔬 Research complete\n"
        f"{job.get('title') or '?'} - {job.get('posted_company_name') or '?'}\n"
        f"Verdict: {assessment.get('apply_verdict') or '?'}\n"
        f"Relevance: {assessment.get('relevance_score') or '?'}\n"
        f"Trust: {trust}\n"
        f"Summary: {assessment.get('one_line_summary') or '?'}\n"
        f"Source: {job.get('apply_url') or job.get('url')}\n"
        f"Dashboard: http://localhost:3000"
    )
    _send(msg)


def research_failed(job_id: int, error: str) -> None:
    pb = get_pb()
    job = pb.get_job(job_id) or {}
    title = job.get("title") or f"job {job_id}"
    company = job.get("posted_company_name") or "?"
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
    parser.add_argument("--run-id", type=int)
    parser.add_argument("--job-id", type=int)
    parser.add_argument("--provider")
    parser.add_argument("--step")
    parser.add_argument("--error")
    parser.add_argument("--artifact-path")
    args = parser.parse_args()

    if args.type == "daily_digest":
        daily_digest(args.run_id)
    elif args.type == "pipeline_failure":
        pipeline_failure(args.provider or "?", args.step or "?",
                         args.error or "unknown", args.artifact_path or "?")
    elif args.type == "research_complete":
        research_complete(args.job_id)
    elif args.type == "research_failed":
        research_failed(args.job_id, args.error or "unknown")


if __name__ == "__main__":
    main()
