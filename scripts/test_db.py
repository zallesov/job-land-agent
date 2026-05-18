import os
import sqlite3
import tempfile
import pytest
from db import create_db, get_connection

def make_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    create_db(path)
    return path

def test_creates_all_tables():
    path = make_db()
    con = get_connection(path)
    tables = {r[0] for r in con.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()}
    expected = {"jobs", "companies", "company_research", "job_assessments",
                "applications", "agent_commands", "pipeline_runs", "events"}
    assert expected.issubset(tables)
    con.close()
    os.unlink(path)

def test_job_url_unique():
    path = make_db()
    con = get_connection(path)
    con.execute(
        "INSERT INTO jobs (url, provider, status) VALUES (?, ?, ?)",
        ("https://example.com/job/1", "greenhouse", "new")
    )
    con.commit()
    with pytest.raises(sqlite3.IntegrityError):
        con.execute(
            "INSERT INTO jobs (url, provider, status) VALUES (?, ?, ?)",
            ("https://example.com/job/1", "greenhouse", "new")
        )
        con.commit()
    con.close()
    os.unlink(path)

def test_foreign_keys_enabled():
    path = make_db()
    con = get_connection(path)
    result = con.execute("PRAGMA foreign_keys").fetchone()
    assert result[0] == 1
    con.close()
    os.unlink(path)

def test_indexes_exist():
    path = make_db()
    con = get_connection(path)
    indexes = {r[1] for r in con.execute(
        "SELECT * FROM sqlite_master WHERE type='index'"
    ).fetchall()}
    for expected_idx in ["idx_jobs_url", "idx_jobs_status", "idx_jobs_provider",
                         "idx_companies_domain", "idx_agent_commands_status"]:
        assert expected_idx in indexes, f"Missing index: {expected_idx}"
    con.close()
    os.unlink(path)
