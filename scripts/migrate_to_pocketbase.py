#!/usr/bin/env python3
"""
Migrate jobs.db → PocketBase.
Creates collections then imports all data with original integer IDs as strings.
"""

import os
import sqlite3
import json
import sys
import requests
from pathlib import Path

_ROOT = Path(__file__).parent.parent
_ENV_FILE = _ROOT / ".env"
if _ENV_FILE.exists():
    for _line in _ENV_FILE.read_text().splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _, _v = _line.partition("=")
            os.environ.setdefault(_k.strip(), _v.strip())

PB_URL = os.environ.get("POCKETBASE_URL", "http://localhost:8090").rstrip("/")
DB_PATH = _ROOT / "jobs.db"
ADMIN_EMAIL = os.environ.get("POCKETBASE_ADMIN_EMAIL", "")
ADMIN_PASSWORD = os.environ.get("POCKETBASE_ADMIN_PASSWORD", "")

# ---------------------------------------------------------------------------
# Collection schemas
# ---------------------------------------------------------------------------

COLLECTIONS = [
    {
        "name": "companies",
        "fields": [
            {"type": "text", "name": "display_name"},
            {"type": "text", "name": "normalized_name"},
            {"type": "text", "name": "website_url"},
            {"type": "text", "name": "domain"},
            {"type": "text", "name": "linkedin_url"},
            {"type": "text", "name": "glassdoor_url"},
            {"type": "text", "name": "crunchbase_url"},
            {"type": "text", "name": "created_at"},
            {"type": "text", "name": "updated_at"},
        ],
    },
    {
        "name": "jobs",
        "fields": [
            {"type": "text", "name": "url"},
            {"type": "text", "name": "provider"},
            {"type": "text", "name": "provider_job_id"},
            {"type": "text", "name": "company_id"},           # FK → companies (string)
            {"type": "text", "name": "posted_company_name"},
            {"type": "text", "name": "actual_hiring_company_id"},  # FK → companies
            {"type": "text", "name": "title"},
            {"type": "text", "name": "description"},
            {"type": "text", "name": "apply_url"},
            {"type": "text", "name": "location"},
            {"type": "text", "name": "country"},
            {"type": "text", "name": "remote_scope"},
            {"type": "text", "name": "date_posted"},
            {"type": "text", "name": "first_seen"},
            {"type": "text", "name": "last_seen"},
            {"type": "text", "name": "status"},
            {"type": "text", "name": "pipeline_status"},
            {"type": "text", "name": "user_status"},
            {"type": "text", "name": "research_status"},
            {"type": "text", "name": "comment"},
            {"type": "text", "name": "current_interview_status"},
            {"type": "json", "name": "source_payload_json"},
            {"type": "text", "name": "deleted_at"},
            {"type": "text", "name": "salary_range"},
            {"type": "text", "name": "dedup_key"},
            {"type": "text", "name": "created_at"},
            {"type": "text", "name": "updated_at"},
        ],
    },
    {
        "name": "company_research",
        "fields": [
            {"type": "text",   "name": "company_id"},
            {"type": "text",   "name": "researched_at"},
            {"type": "text",   "name": "research_status"},
            {"type": "text",   "name": "legitimacy_check"},
            {"type": "text",   "name": "hiring_entity_type"},
            {"type": "number", "name": "founded_year"},
            {"type": "text",   "name": "hq_location"},
            {"type": "text",   "name": "employee_count"},
            {"type": "text",   "name": "headcount_trend"},
            {"type": "text",   "name": "funding_summary"},
            {"type": "text",   "name": "funding_stage"},
            {"type": "text",   "name": "risk_news"},
            {"type": "text",   "name": "glassdoor_summary"},
            {"type": "number", "name": "trustworthiness_score"},
            {"type": "text",   "name": "research_notes"},
            {"type": "json",   "name": "source_urls_json"},
            {"type": "json",   "name": "raw_research_json"},
            {"type": "text",   "name": "created_at"},
            {"type": "text",   "name": "updated_at"},
        ],
    },
    {
        "name": "job_assessments",
        "fields": [
            {"type": "text",   "name": "job_id"},
            {"type": "text",   "name": "assessed_at"},
            {"type": "text",   "name": "assessment_status"},
            {"type": "number", "name": "relevance_score"},
            {"type": "text",   "name": "apply_verdict"},
            {"type": "text",   "name": "one_line_summary"},
            {"type": "text",   "name": "red_flag_scan"},
            {"type": "text",   "name": "seniority_fit"},
            {"type": "text",   "name": "tech_stack_fit"},
            {"type": "text",   "name": "ic_or_management"},
            {"type": "text",   "name": "salary_assessment"},
            {"type": "text",   "name": "remote_eligibility"},
            {"type": "text",   "name": "visa_contract_structure"},
            {"type": "text",   "name": "ai_native_assessment"},
            {"type": "text",   "name": "assessment_notes"},
            {"type": "json",   "name": "source_urls_json"},
            {"type": "json",   "name": "raw_assessment_json"},
            {"type": "text",   "name": "created_at"},
            {"type": "text",   "name": "updated_at"},
        ],
    },
    {
        "name": "applications",
        "fields": [
            {"type": "text", "name": "job_id"},
            {"type": "text", "name": "status"},
            {"type": "text", "name": "tailored_cv_path"},
            {"type": "text", "name": "cover_letter_path"},
            {"type": "text", "name": "application_notes_path"},
            {"type": "text", "name": "created_at"},
            {"type": "text", "name": "submitted_at"},
            {"type": "text", "name": "updated_at"},
            {"type": "text", "name": "error"},
        ],
    },
    {
        "name": "agent_commands",
        "fields": [
            {"type": "text", "name": "command_type"},
            {"type": "json", "name": "payload_json"},
            {"type": "text", "name": "status"},
            {"type": "text", "name": "created_by"},
            {"type": "text", "name": "created_at"},
            {"type": "text", "name": "started_at"},
            {"type": "text", "name": "finished_at"},
            {"type": "json", "name": "result_json"},
            {"type": "text", "name": "error"},
        ],
    },
    {
        "name": "pipeline_runs",
        "fields": [
            {"type": "text", "name": "run_type"},
            {"type": "text", "name": "status"},
            {"type": "text", "name": "started_at"},
            {"type": "text", "name": "finished_at"},
            {"type": "json", "name": "summary_json"},
            {"type": "text", "name": "error"},
        ],
    },
    {
        "name": "events",
        "fields": [
            {"type": "text", "name": "entity_type"},
            {"type": "text", "name": "entity_id"},
            {"type": "text", "name": "event_type"},
            {"type": "text", "name": "actor"},
            {"type": "json", "name": "event_json"},
            {"type": "text", "name": "created_at"},
        ],
    },
    {
        "name": "interviews",
        "fields": [
            {"type": "text", "name": "company_name"},
            {"type": "text", "name": "job_title"},
            {"type": "text", "name": "status"},
            {"type": "text", "name": "interview_status"},
            {"type": "text", "name": "next_interview_date"},
            {"type": "json", "name": "interview_dates_json"},
            {"type": "text", "name": "description"},
            {"type": "text", "name": "contacts"},
            {"type": "text", "name": "contact_via"},
            {"type": "text", "name": "telegram_handle"},
            {"type": "text", "name": "job_url"},
            {"type": "text", "name": "comments"},
            {"type": "json", "name": "contacts_json"},
            {"type": "json", "name": "emails_json"},
            {"type": "text", "name": "job_id"},
            {"type": "text", "name": "created_at"},
            {"type": "text", "name": "updated_at"},
        ],
    },
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def auth(session: requests.Session) -> str:
    resp = session.post(
        f"{PB_URL}/api/collections/_superusers/auth-with-password",
        json={"identity": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
    )
    resp.raise_for_status()
    token = resp.json()["token"]
    session.headers.update({"Authorization": token})
    return token


def existing_collections(session: requests.Session) -> set[str]:
    resp = session.get(f"{PB_URL}/api/collections?perPage=200")
    resp.raise_for_status()
    return {c["name"] for c in resp.json().get("items", [])}


def create_collection(session: requests.Session, schema: dict) -> None:
    payload = {
        "name": schema["name"],
        "type": "base",
        "fields": schema["fields"],
        "listRule": "",
        "viewRule": "",
        "createRule": "",
        "updateRule": "",
        "deleteRule": "",
    }
    resp = session.post(f"{PB_URL}/api/collections", json=payload)
    if resp.status_code == 400 and "already exists" in resp.text:
        print(f"  collection '{schema['name']}' already exists, skipping")
        return
    resp.raise_for_status()
    print(f"  created collection '{schema['name']}'")


def row_to_dict(cursor: sqlite3.Cursor, row: tuple) -> dict:
    return {col[0]: val for col, val in zip(cursor.description, row)}


FK_FIELDS = {"company_id", "job_id", "actual_hiring_company_id", "entity_id"}


def pb_id(val) -> str:
    """Pad integer ID to PocketBase minimum 15-char ID."""
    return str(val).zfill(15)


def clean(record: dict) -> dict:
    """Convert int ID to 15-char padded string, nulls dropped, FK fields padded."""
    out = {}
    for k, v in record.items():
        if k == "id":
            out["id"] = pb_id(v)
        elif v is None:
            pass  # omit nulls
        elif k in FK_FIELDS and v is not None:
            out[k] = pb_id(v)
        elif isinstance(v, int):
            out[k] = v
        else:
            out[k] = v
    return out


def import_table(session: requests.Session, db: sqlite3.Connection, table: str) -> None:
    cur = db.execute(f"SELECT * FROM {table}")
    rows = cur.fetchall()
    if not rows:
        print(f"  '{table}': empty, skipping")
        return

    ok = err = 0
    for row in rows:
        record = clean(row_to_dict(cur, row))
        resp = session.post(
            f"{PB_URL}/api/collections/{table}/records",
            json=record,
        )
        if resp.status_code in (200, 201):
            ok += 1
        elif resp.status_code == 400 and "already exists" in resp.text:
            ok += 1  # idempotent re-run
        else:
            err += 1
            if err <= 3:
                print(f"    ERR row id={record.get('id')}: {resp.status_code} {resp.text[:200]}")
    print(f"  '{table}': {ok} ok, {err} errors")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    if not DB_PATH.exists():
        print(f"ERROR: {DB_PATH} not found")
        sys.exit(1)

    session = requests.Session()
    print("Authenticating...")
    auth(session)

    print("\nCreating collections...")
    existing = existing_collections(session)
    for schema in COLLECTIONS:
        if schema["name"] in existing:
            print(f"  '{schema['name']}' already exists, skipping")
        else:
            create_collection(session, schema)

    print("\nMigrating data...")
    db = sqlite3.connect(DB_PATH)
    # Order matters: parents before children
    order = [
        "companies",
        "jobs",
        "company_research",
        "job_assessments",
        "applications",
        "agent_commands",
        "pipeline_runs",
        "events",
        "interviews",
    ]
    for table in order:
        import_table(session, db, table)
    db.close()

    print("\nDone.")


if __name__ == "__main__":
    main()
