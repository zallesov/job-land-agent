#!/usr/bin/env python3
"""
Apply cheap non-AI tags to newly inserted jobs.
Tags are stored merged into source_payload_json.
Never suppresses, archives, or deletes jobs.

Usage:
  python3 tag_new_jobs.py --db jobs.db [--since-hours 25]
"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from db import get_connection

ROLE_KEYWORDS = {
    "engineering_manager": [
        "engineering manager", "engineering lead", "engineering director",
        "head of engineering", "vp of engineering", "vp engineering",
        "director of engineering", "eng manager", "eng lead",
    ],
    "ai_engineer": ["ai engineer", "ml engineer", "machine learning", "llm", "generative ai"],
    "backend": ["backend", "back-end", "server-side", "api engineer", "platform engineer"],
    "frontend": ["frontend", "front-end", "react engineer", "vue engineer", "ui engineer"],
    "fullstack": ["full stack", "fullstack", "full-stack"],
    "staff_plus": ["staff engineer", "principal engineer", "distinguished engineer"],
}

SENIORITY_KEYWORDS = {
    "senior": ["senior", "sr.", "sr "],
    "staff_plus": ["staff", "principal", "distinguished", "fellow"],
    "manager": ["manager", "director", "vp ", "head of"],
    "mid": ["mid-level", "mid level"],
    "junior": ["junior", "jr.", "jr ", "graduate", "entry level"],
}

AI_KEYWORDS = ["llm", "gpt", "ai ", " ai,", "machine learning", "generative", "rag", "vector db",
               "embedding", "anthropic", "openai", "claude"]
RECRUITER_KEYWORDS = ["via recruiter", "recruiting agency", " agency ", "talent acquisition",
                      "staffing", "search firm"]


def classify(title: str, description: str) -> dict:
    text = f"{title} {description}".lower()
    title_lower = title.lower()

    role = "other"
    for r, kws in ROLE_KEYWORDS.items():
        if any(k in text for k in kws):
            role = r
            break

    seniority = "unknown"
    for s, kws in SENIORITY_KEYWORDS.items():
        if any(k in title_lower for k in kws):
            seniority = s
            break

    ai_relevant = any(k in text for k in AI_KEYWORDS)
    recruiter_hint = any(k in text for k in RECRUITER_KEYWORDS)

    remote_signal = "unknown"
    if "fully remote" in text or "100% remote" in text:
        remote_signal = "fully_remote"
    elif "remote" in text and "hybrid" in text:
        remote_signal = "hybrid"
    elif "remote" in text:
        remote_signal = "remote"
    elif "on-site" in text or "onsite" in text:
        remote_signal = "onsite"

    salary_missing = not bool(re.search(r"\$[\d,]+|\€[\d,]+|[\d,]+k|\bsalary\b", text))

    return {
        "light_role": role,
        "light_seniority": seniority,
        "light_ai_relevant": ai_relevant,
        "light_remote_signal": remote_signal,
        "light_salary_missing": salary_missing,
        "light_recruiter_hint": recruiter_hint,
    }


def tag_new_jobs(db_path: str, since_hours: int = 25) -> dict:
    con = get_connection(db_path)
    jobs = con.execute(
        "SELECT id, title, description, source_payload_json FROM jobs "
        "WHERE first_seen >= datetime('now', ?)",
        (f"-{since_hours} hours",)
    ).fetchall()

    tagged = 0
    for job in jobs:
        tags = classify(job["title"] or "", job["description"] or "")
        existing: dict = {}
        if job["source_payload_json"]:
            try:
                existing = json.loads(job["source_payload_json"])
            except Exception:
                pass
        existing.update(tags)
        con.execute(
            "UPDATE jobs SET source_payload_json = ?, updated_at = datetime('now') WHERE id = ?",
            (json.dumps(existing), job["id"])
        )
        tagged += 1

    con.commit()
    con.close()
    return {"tagged": tagged}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", required=True)
    parser.add_argument("--since-hours", type=int, default=25)
    args = parser.parse_args()
    result = tag_new_jobs(args.db, args.since_hours)
    print(f"Tagged {result['tagged']} jobs")


if __name__ == "__main__":
    main()
