"""T9 wiring — wellfound_ingest maps shortlist rows -> status=new records via MCP."""
import json
from scripts.wellfound_ingest import _row_to_shallow, load_rows, main


def test_row_to_shallow_maps_fields():
    j = _row_to_shallow({
        "url": "https://wellfound.com/jobs/1", "title": "Eng", "company": "Acme",
        "location": "Berlin", "compensation": "$100k", "posted": "2d ago",
    })
    assert j.provider == "wellfound"
    assert j.dedup_key == "Acme::Eng"
    assert j.salary_raw == "$100k"
    assert j.status == "new"


def test_ingest_inserts_as_new(tmp_path, mcp):
    f = tmp_path / "shortlist_new.json"
    f.write_text(json.dumps([
        {"url": "https://wellfound.com/jobs/1", "title": "A", "company": "C1"},
        {"url": "https://wellfound.com/jobs/2", "title": "B", "company": "C2"},
        {"title": "no-url"},  # dropped (no url)
    ]))
    main([str(f)])
    rows = mcp.list_all_jobs("")
    assert len(rows) == 2
    assert all(r["status"] == "new" and r["provider"] == "wellfound" for r in rows)
    assert "pipeline_status" not in rows[0]


def test_load_rows_accepts_dict_and_list(tmp_path):
    p = tmp_path / "d.json"
    p.write_text(json.dumps({"jobs": [{"url": "u", "title": "t"}]}))
    assert load_rows(p) == [{"url": "u", "title": "t"}]
    p.write_text(json.dumps([{"url": "u2", "title": "t2"}]))
    assert load_rows(p) == [{"url": "u2", "title": "t2"}]
