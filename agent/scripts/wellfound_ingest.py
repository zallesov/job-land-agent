#!/usr/bin/env python3
"""Ingest deduped WellFound shallow rows into JobLand as status=new (via MCP).

Pipeline step 6: takes the post-dedup shortlist (new jobs only, not yet in the DB) and
inserts each as a `status=new` record through JobLandMCP. Enrichment (step 8) later picks
these up by `status=new` and advances them to `enriched`.

    python3 scripts/wellfound_ingest.py tmp/wellfound/shortlist_new.json

Reuses pipeline.ingest.ingest_jobs (single MCP write path); duplicate URLs are skipped
silently there. DB access is JobLandMCP-only.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.pipeline.ingest import ingest_jobs  # noqa: E402
from scripts.pipeline.types import ShallowJob  # noqa: E402


def _row_to_shallow(row: dict) -> ShallowJob:
    company = row.get("company") or ""
    title = row.get("title") or ""
    return ShallowJob(
        provider="wellfound",
        title=title,
        company=company,
        url=row.get("url") or "",
        location=row.get("location") or "",
        country=row.get("country") or None,
        dedup_key=row.get("dedup_key") or (f"{company}::{title}" if company and title else ""),
        posting_date=row.get("posted") or row.get("postingDate") or None,
        salary_raw=row.get("compensation") or row.get("salary") or row.get("salaryRaw") or None,
        status="new",
    )


def load_rows(path: Path) -> list[dict]:
    data = json.loads(path.read_text())
    if isinstance(data, dict):
        return data.get("jobs", [])
    return data


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("input", nargs="?", default=str(ROOT / "tmp/wellfound/shortlist_new.json"))
    args = ap.parse_args(argv)

    rows = load_rows(Path(args.input))
    jobs = [_row_to_shallow(r) for r in rows if (r.get("url") and r.get("title"))]
    ids = ingest_jobs(jobs)
    print(f"[ingest] {len(ids)} new wellfound jobs inserted (status=new) from {len(rows)} rows",
          flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
