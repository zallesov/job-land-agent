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
                         "idx_jobs_country", "idx_jobs_company_id",
                         "idx_companies_domain", "idx_companies_normalized_name",
                         "idx_agent_commands_status", "idx_pipeline_runs_started_at"]:
        assert expected_idx in indexes, f"Missing index: {expected_idx}"
    con.close()
    os.unlink(path)


# --- Task 1: get_job / update_job_status / dedup_key ---

def test_get_job_returns_dict():
    from db import get_job
    path = make_db()
    con = get_connection(path)
    jid = con.execute(
        "INSERT INTO jobs (url, provider, status) VALUES ('http://x.com','test','new')"
    ).lastrowid
    con.commit()
    job = get_job(con, jid)
    assert job["id"] == jid
    assert job["status"] == "new"
    con.close()
    os.unlink(path)


def test_get_job_missing_returns_none():
    from db import get_job
    path = make_db()
    con = get_connection(path)
    assert get_job(con, 99999) is None
    con.close()
    os.unlink(path)


def test_update_job_status():
    from db import get_job, update_job_status
    path = make_db()
    con = get_connection(path)
    jid = con.execute(
        "INSERT INTO jobs (url, provider, status) VALUES ('http://x.com','test','listed')"
    ).lastrowid
    con.commit()
    update_job_status(con, jid, "enrich_failed", comment="timeout")
    con.commit()
    job = get_job(con, jid)
    assert job["status"] == "enrich_failed"
    assert job["comment"] == "timeout"
    con.close()
    os.unlink(path)


def test_dedup_key_column_exists():
    path = make_db()
    con = get_connection(path)
    con.execute("INSERT INTO jobs (url, provider, dedup_key) VALUES ('http://y.com','test','Co::Title')")
    con.commit()
    row = con.execute("SELECT dedup_key FROM jobs WHERE url='http://y.com'").fetchone()
    assert row["dedup_key"] == "Co::Title"
    con.close()
    os.unlink(path)


def test_dedup_key_unique():
    path = make_db()
    con = get_connection(path)
    con.execute("INSERT INTO jobs (url, provider, dedup_key) VALUES ('http://a.com','t','Co::T')")
    con.commit()
    with pytest.raises(Exception):
        con.execute("INSERT INTO jobs (url, provider, dedup_key) VALUES ('http://b.com','t','Co::T')")
        con.commit()
    con.close()
    os.unlink(path)
