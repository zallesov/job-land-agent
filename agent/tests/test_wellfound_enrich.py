"""T5 — enrich writes each finished job back to JobLand (status=enriched) per job.

Covers the pure, hermetic pieces (no browser, no network): the field mapping, the
persist gate (so a bot-blocked job is never advanced), and the per-job DB write via a
FakeMCPClient. The Playwright-driven parts are exercised by the live smoke run.
"""
from scripts.wellfound_enrich import to_jobland_fields, should_persist, persist


# --- field mapping ---

def test_to_jobland_fields_maps_and_omits_empty():
    rec = {
        "id": "x", "title": "Senior Eng", "company": "Acme",
        "apply_url": "http://ats/apply", "description": "do things",
        "compensation": "$100k", "locations": ["Berlin", "Remote"], "remote": True,
    }
    f = to_jobland_fields(rec)
    assert f == {
        "title": "Senior Eng",
        "posted_company_name": "Acme",
        "apply_url": "http://ats/apply",
        "description": "do things",
        "salary_range": "$100k",        # PB field name, not salary_raw
        "location": "Berlin, Remote",
        "remote_scope": "remote",
    }


def test_to_jobland_fields_drops_empties_and_non_remote():
    f = to_jobland_fields({"title": "T", "company": "", "remote": False, "locations": []})
    assert f == {"title": "T"}   # empty company, no remote_scope, no location


# --- persist gate ---

def test_should_persist_true_for_enriched_with_id():
    assert should_persist({"id": "1", "enriched": True}) is True


def test_should_persist_false_when_blocked():
    assert should_persist({"id": "1", "enriched": False, "blocked": True}) is False


def test_should_persist_false_without_id():
    assert should_persist({"enriched": True}) is False


def test_should_persist_false_when_not_enriched():
    assert should_persist({"id": "1", "enriched": False}) is False


# --- per-job DB write ---

def test_persist_advances_job_to_enriched(mcp):
    mcp.create("jobs", {"id": "j1", "url": "http://wf/1", "provider": "wellfound", "status": "new"})
    rec = {"id": "j1", "enriched": True, "company": "Acme", "title": "Eng",
           "description": "desc", "compensation": "$90k"}
    assert persist(mcp, rec) is True
    row = mcp.get_job("j1")
    assert row["status"] == "enriched"
    assert row["posted_company_name"] == "Acme"
    assert row["salary_range"] == "$90k"


def test_persist_skips_blocked_job_leaving_status_new(mcp):
    mcp.create("jobs", {"id": "j2", "url": "http://wf/2", "provider": "wellfound", "status": "new"})
    blocked = {"id": "j2", "blocked": True, "enriched": False}
    assert persist(mcp, blocked) is False
    assert mcp.get_job("j2")["status"] == "new"   # not advanced — next run retries it
