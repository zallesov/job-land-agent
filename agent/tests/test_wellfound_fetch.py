"""T6 — wellfound_fetch helper returns only the requested provider+status."""
from scripts.wellfound_fetch import build_filter, fetch_jobs


def _seed(mcp):
    mcp.insert_job(url="http://wf1", provider="wellfound", status="new", title="A")
    mcp.insert_job(url="http://wf2", provider="wellfound", status="enriched", title="B")
    mcp.insert_job(url="http://wf3", provider="wellfound", status="new", title="C")
    mcp.insert_job(url="http://sp1", provider="sprout", status="new", title="D")


def test_build_filter():
    assert build_filter("wellfound", "new") == 'provider = "wellfound" && status = "new"'
    assert build_filter("wellfound", None) == 'provider = "wellfound"'


def test_fetch_filters_provider_and_status(mcp):
    _seed(mcp)
    rows = fetch_jobs("wellfound", "new", client=mcp)
    titles = sorted(r["title"] for r in rows)
    assert titles == ["A", "C"]  # not the enriched wellfound, not the sprout one


def test_fetch_provider_only(mcp):
    _seed(mcp)
    rows = fetch_jobs("wellfound", None, client=mcp)
    assert sorted(r["title"] for r in rows) == ["A", "B", "C"]


def test_fetch_excludes_other_provider(mcp):
    _seed(mcp)
    rows = fetch_jobs("sprout", "new", client=mcp)
    assert [r["title"] for r in rows] == ["D"]


def test_fetch_escapes_quotes():
    # no crash, value embedded safely
    f = build_filter('we"ird', "new")
    assert '\\"' in f
