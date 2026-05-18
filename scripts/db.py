import re
import sqlite3
from pathlib import Path


def get_connection(db_path: str) -> sqlite3.Connection:
    con = sqlite3.connect(db_path)
    con.execute("PRAGMA foreign_keys = ON")
    con.execute("PRAGMA journal_mode = WAL")
    con.row_factory = sqlite3.Row
    return con


def create_db(db_path: str) -> None:
    con = get_connection(db_path)
    cur = con.cursor()

    cur.executescript("""
    CREATE TABLE IF NOT EXISTS companies (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        display_name TEXT NOT NULL,
        normalized_name TEXT NOT NULL,
        website_url TEXT,
        domain TEXT,
        linkedin_url TEXT,
        glassdoor_url TEXT,
        crunchbase_url TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS jobs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        url TEXT NOT NULL UNIQUE,
        provider TEXT NOT NULL,
        provider_job_id TEXT,
        company_id INTEGER REFERENCES companies(id),
        posted_company_name TEXT,
        actual_hiring_company_id INTEGER REFERENCES companies(id),
        title TEXT,
        description TEXT,
        apply_url TEXT,
        location TEXT,
        country TEXT,
        remote_scope TEXT,
        date_posted TEXT,
        first_seen TEXT NOT NULL DEFAULT (datetime('now')),
        last_seen TEXT NOT NULL DEFAULT (datetime('now')),
        status TEXT NOT NULL DEFAULT 'new',
        comment TEXT,
        current_interview_status TEXT,
        source_payload_json TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS company_research (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        company_id INTEGER NOT NULL REFERENCES companies(id),
        researched_at TEXT,
        research_status TEXT NOT NULL DEFAULT 'pending',
        legitimacy_check TEXT,
        hiring_entity_type TEXT,
        founded_year INTEGER,
        hq_location TEXT,
        employee_count TEXT,
        headcount_trend TEXT,
        funding_summary TEXT,
        funding_stage TEXT,
        risk_news TEXT,
        glassdoor_summary TEXT,
        trustworthiness_score INTEGER,
        research_notes TEXT,
        source_urls_json TEXT,
        raw_research_json TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS job_assessments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id INTEGER NOT NULL UNIQUE REFERENCES jobs(id),
        assessed_at TEXT,
        assessment_status TEXT NOT NULL DEFAULT 'pending',
        relevance_score INTEGER,
        apply_verdict TEXT,
        one_line_summary TEXT,
        red_flag_scan TEXT,
        seniority_fit TEXT,
        tech_stack_fit TEXT,
        ic_or_management TEXT,
        salary_assessment TEXT,
        remote_eligibility TEXT,
        visa_contract_structure TEXT,
        ai_native_assessment TEXT,
        assessment_notes TEXT,
        source_urls_json TEXT,
        raw_assessment_json TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS applications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id INTEGER NOT NULL REFERENCES jobs(id),
        status TEXT NOT NULL DEFAULT 'draft_requested',
        tailored_cv_path TEXT,
        cover_letter_path TEXT,
        application_notes_path TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        submitted_at TEXT,
        updated_at TEXT NOT NULL DEFAULT (datetime('now')),
        error TEXT
    );

    CREATE TABLE IF NOT EXISTS agent_commands (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        command_type TEXT NOT NULL,
        payload_json TEXT,
        status TEXT NOT NULL DEFAULT 'pending',
        created_by TEXT NOT NULL DEFAULT 'system',
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        started_at TEXT,
        finished_at TEXT,
        result_json TEXT,
        error TEXT
    );

    CREATE TABLE IF NOT EXISTS pipeline_runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_type TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'running',
        started_at TEXT NOT NULL DEFAULT (datetime('now')),
        finished_at TEXT,
        summary_json TEXT,
        error TEXT
    );

    CREATE TABLE IF NOT EXISTS events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        entity_type TEXT NOT NULL,
        entity_id INTEGER,
        event_type TEXT NOT NULL,
        actor TEXT NOT NULL DEFAULT 'system',
        event_json TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    );

    CREATE UNIQUE INDEX IF NOT EXISTS idx_jobs_url ON jobs(url);
    CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
    CREATE INDEX IF NOT EXISTS idx_jobs_provider ON jobs(provider);
    CREATE INDEX IF NOT EXISTS idx_jobs_country ON jobs(country);
    CREATE INDEX IF NOT EXISTS idx_jobs_company_id ON jobs(company_id);
    CREATE INDEX IF NOT EXISTS idx_companies_domain ON companies(domain);
    CREATE INDEX IF NOT EXISTS idx_companies_normalized_name ON companies(normalized_name);
    CREATE INDEX IF NOT EXISTS idx_agent_commands_status ON agent_commands(status);
    CREATE INDEX IF NOT EXISTS idx_pipeline_runs_started_at ON pipeline_runs(started_at);
    """)

    con.commit()
    con.close()


def _normalize_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower().strip())


def upsert_company(con: sqlite3.Connection, display_name: str, domain: str | None = None) -> int:
    normalized = _normalize_name(display_name)
    if domain:
        row = con.execute("SELECT id FROM companies WHERE domain = ?", (domain,)).fetchone()
    else:
        row = con.execute(
            "SELECT id FROM companies WHERE normalized_name = ? AND domain IS NULL",
            (normalized,)
        ).fetchone()
    if row:
        return row["id"]
    cur = con.execute(
        "INSERT INTO companies (display_name, normalized_name, domain) VALUES (?, ?, ?)",
        (display_name, normalized, domain)
    )
    return cur.lastrowid


def get_job_by_url(con: sqlite3.Connection, url: str) -> sqlite3.Row | None:
    return con.execute("SELECT * FROM jobs WHERE url = ?", (url,)).fetchone()


def insert_job(con: sqlite3.Connection, **fields) -> int:
    cols = ", ".join(fields.keys())
    placeholders = ", ".join("?" * len(fields))
    cur = con.execute(
        f"INSERT INTO jobs ({cols}) VALUES ({placeholders})",
        list(fields.values())
    )
    return cur.lastrowid


def update_job_machine_fields(con: sqlite3.Connection, job_id: int, **fields) -> None:
    PROTECTED = {"status", "comment", "current_interview_status"}
    safe = {k: v for k, v in fields.items() if k not in PROTECTED}
    if not safe:
        return
    set_parts = [f"{k} = ?" for k in safe]
    set_parts.append("updated_at = datetime('now')")
    params = list(safe.values()) + [job_id]
    con.execute(
        f"UPDATE jobs SET {', '.join(set_parts)} WHERE id = ?",
        params
    )


def log_event(con: sqlite3.Connection, entity_type: str, entity_id: int,
              event_type: str, actor: str = "system", event_json: str | None = None) -> None:
    con.execute(
        "INSERT INTO events (entity_type, entity_id, event_type, actor, event_json) "
        "VALUES (?, ?, ?, ?, ?)",
        (entity_type, entity_id, event_type, actor, event_json)
    )


def create_pipeline_run(con: sqlite3.Connection, run_type: str) -> int:
    cur = con.execute(
        "INSERT INTO pipeline_runs (run_type, status) VALUES (?, 'running')",
        (run_type,)
    )
    return cur.lastrowid


def finish_pipeline_run(con: sqlite3.Connection, run_id: int, status: str,
                        summary_json: str | None = None, error: str | None = None) -> None:
    con.execute(
        "UPDATE pipeline_runs SET status = ?, finished_at = datetime('now'), "
        "summary_json = ?, error = ? WHERE id = ?",
        (status, summary_json, error, run_id)
    )
