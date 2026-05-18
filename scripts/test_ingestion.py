import json
import os
import tempfile
import pytest
import sys
sys.path.insert(0, os.path.dirname(__file__))

from db import create_db, get_connection
from ingest_provider_outputs import normalize_job, ingest_run_file, find_latest_run_files

SAMPLE_JOB = {
    "provider": "greenhouse",
    "company": "Acme Corp",
    "title": "Senior Engineer",
    "url": "https://job-boards.greenhouse.io/acme/jobs/123",
    "description": "Build stuff. Remote friendly.",
    "applyUrl": "https://job-boards.greenhouse.io/acme/jobs/123",
    "location": "Remote",
    "country": "Germany",
    "postingDate": "2026-05-18",
    "searchLabel": "Software Engineer - Berlin Remote",
    "searchQuery": "Software Engineer"
}

def make_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    create_db(path)
    return path

def make_run_file(jobs: list) -> str:
    fd, path = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    with open(path, "w") as f:
        json.dump(jobs, f)
    return path

def test_normalize_job_maps_fields():
    n = normalize_job(SAMPLE_JOB)
    assert n["url"] == SAMPLE_JOB["url"]
    assert n["provider"] == "greenhouse"
    assert n["posted_company_name"] == "Acme Corp"
    assert n["date_posted"] == "2026-05-18"
    assert "source_payload" in n

def test_ingest_inserts_job_and_company():
    db_path = make_db()
    run_path = make_run_file([SAMPLE_JOB])
    result = ingest_run_file(db_path, run_path)
    assert result["inserted"] == 1
    assert result["updated"] == 0
    assert result["failed"] == 0
    con = get_connection(db_path)
    job = con.execute("SELECT * FROM jobs WHERE url = ?", (SAMPLE_JOB["url"],)).fetchone()
    assert job is not None
    assert job["title"] == "Senior Engineer"
    company = con.execute("SELECT * FROM companies WHERE id = ?", (job["company_id"],)).fetchone()
    assert company is not None
    assert company["display_name"] == "Acme Corp"
    con.close()
    os.unlink(db_path)
    os.unlink(run_path)

def test_ingest_dedupes_by_url():
    db_path = make_db()
    run_path = make_run_file([SAMPLE_JOB])
    ingest_run_file(db_path, run_path)
    result = ingest_run_file(db_path, run_path)
    assert result["inserted"] == 0
    assert result["updated"] == 1
    con = get_connection(db_path)
    count = con.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
    assert count == 1
    con.close()
    os.unlink(db_path)
    os.unlink(run_path)

def test_ingest_preserves_manual_fields():
    db_path = make_db()
    run_path = make_run_file([SAMPLE_JOB])
    ingest_run_file(db_path, run_path)
    con = get_connection(db_path)
    con.execute(
        "UPDATE jobs SET status = 'interesting', comment = 'looks good' WHERE url = ?",
        (SAMPLE_JOB["url"],)
    )
    con.commit()
    con.close()
    ingest_run_file(db_path, run_path)
    con = get_connection(db_path)
    job = con.execute("SELECT * FROM jobs WHERE url = ?", (SAMPLE_JOB["url"],)).fetchone()
    assert job["status"] == "interesting"
    assert job["comment"] == "looks good"
    con.close()
    os.unlink(db_path)
    os.unlink(run_path)

def test_ingest_same_company_normalized_name_one_record():
    db_path = make_db()
    job2 = {**SAMPLE_JOB, "url": "https://job-boards.greenhouse.io/acme/jobs/456", "title": "PM"}
    run_path = make_run_file([SAMPLE_JOB, job2])
    ingest_run_file(db_path, run_path)
    con = get_connection(db_path)
    count = con.execute("SELECT COUNT(*) FROM companies").fetchone()[0]
    assert count == 1
    con.close()
    os.unlink(db_path)
    os.unlink(run_path)

def test_ingest_malformed_json_returns_error():
    db_path = make_db()
    fd, run_path = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    with open(run_path, "w") as f:
        f.write("not valid json {{{")
    result = ingest_run_file(db_path, run_path)
    assert result.get("error") is not None or result["failed"] > 0
    con = get_connection(db_path)
    count = con.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
    assert count == 0
    con.close()
    os.unlink(db_path)
    os.unlink(run_path)

def test_ingest_merges_source_payload_on_update():
    db_path = make_db()
    run_path = make_run_file([SAMPLE_JOB])
    ingest_run_file(db_path, run_path)
    # Simulate tag_new_jobs adding light_ tags to source_payload_json
    con = get_connection(db_path)
    con.execute(
        "UPDATE jobs SET source_payload_json = ? WHERE url = ?",
        (json.dumps({"light_seniority": "senior", "light_ai_relevant": True}), SAMPLE_JOB["url"])
    )
    con.commit()
    con.close()
    # Re-ingest same job
    ingest_run_file(db_path, run_path)
    con = get_connection(db_path)
    job = con.execute("SELECT source_payload_json FROM jobs WHERE url = ?", (SAMPLE_JOB["url"],)).fetchone()
    payload = json.loads(job["source_payload_json"])
    assert payload.get("light_seniority") == "senior", "light_ tags must be preserved on re-ingest"
    assert payload.get("light_ai_relevant") is True
    con.close()
    os.unlink(db_path)
    os.unlink(run_path)

def test_pipeline_run_record_created():
    db_path = make_db()
    run_path = make_run_file([SAMPLE_JOB])
    ingest_run_file(db_path, run_path)
    con = get_connection(db_path)
    run = con.execute("SELECT * FROM pipeline_runs ORDER BY id DESC LIMIT 1").fetchone()
    assert run is not None
    assert run["status"] in ("succeeded", "partial", "failed")
    con.close()
    os.unlink(db_path)
    os.unlink(run_path)
