"""T7 — scripts/dedup_jobs.py: first dedup by dedup_key (scraped vs existing-from-MCP).

Two input files in (scraped batch + existing JobLand rows), one deduped file out.
Drops: rows whose key is already tracked in JobLand, and in-batch duplicates.
"""
import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / "scripts" / "dedup_jobs.py"


def _run(tmp_path, scraped, existing, by="dedup_key"):
    inp = tmp_path / "scraped.json"
    exi = tmp_path / "existing.json"
    out = tmp_path / "new.json"
    skip = tmp_path / "skipped.json"
    inp.write_text(json.dumps(scraped))
    exi.write_text(json.dumps(existing))
    r = subprocess.run(
        [sys.executable, str(SCRIPT), str(inp),
         "--existing", str(exi), "--out", str(out), "--skipped", str(skip), "--by", by],
        capture_output=True, text=True,
    )
    assert r.returncode == 0, r.stderr
    return json.loads(out.read_text()), json.loads(skip.read_text())


def test_drops_already_tracked_and_in_batch_dupes(tmp_path):
    # existing = what MCP returned for the provider (list of job objects)
    existing = [{"dedup_key": "Acme::SWE", "url": "http://acme/swe"}]
    scraped = [
        {"dedup_key": "Acme::SWE", "url": "http://acme/swe"},   # already tracked -> drop
        {"dedup_key": "New::Co", "url": "http://new/co"},        # new -> keep
        {"dedup_key": "New::Co", "url": "http://new/co2"},       # in-batch dupe -> drop
    ]
    new, skipped = _run(tmp_path, scraped, existing)
    assert new["count"] == 1
    assert new["jobs"][0]["dedup_key"] == "New::Co"
    assert skipped["count"] == 2
    reasons = {j["dedup_reason"] for j in skipped["jobs"]}
    assert reasons == {"dedup_key"}


def test_all_new_when_existing_empty(tmp_path):
    scraped = [{"dedup_key": "A::1"}, {"dedup_key": "B::2"}]
    new, skipped = _run(tmp_path, scraped, [])
    assert new["count"] == 2
    assert skipped["count"] == 0


def test_dedup_key_is_case_insensitive(tmp_path):
    existing = [{"dedup_key": "Acme::SWE"}]
    scraped = [{"dedup_key": "acme::swe"}]  # same role, different case
    new, skipped = _run(tmp_path, scraped, existing)
    assert new["count"] == 0
    assert skipped["count"] == 1
