#!/usr/bin/env python3
"""
Merge all partial scrape JSONs for a provider+date into one canonical run file.

Partial files: outputs/<provider>/runs/<provider>_jobs_live_<date>_<slug>.json
Output:        outputs/<provider>/runs/<provider>_jobs_live_<date>.json

Deduplication key: url (first occurrence wins).

Usage:
  python3 scripts/consolidate_provider_run.py --provider greenhouse
  python3 scripts/consolidate_provider_run.py --provider jobleads --date 2026-05-19
  python3 scripts/consolidate_provider_run.py --provider greenhouse \
    --runs-dir outputs/greenhouse/runs
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", required=True, choices=["greenhouse", "jobleads"])
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--runs-dir", type=Path)
    args = parser.parse_args()

    runs_dir = args.runs_dir or PROJECT_ROOT / "outputs" / args.provider / "runs"
    if not runs_dir.exists():
        print(f"Runs dir not found: {runs_dir}", file=sys.stderr)
        return 1

    pattern = f"{args.provider}_jobs_live_{args.date}_*.json"
    partial_files = sorted(runs_dir.glob(pattern))
    if not partial_files:
        print(f"No partial files matching {pattern} in {runs_dir}", file=sys.stderr)
        return 1

    print(f"Merging {len(partial_files)} partial files for {args.provider} {args.date}:", flush=True)
    for f in partial_files:
        print(f"  {f.name}", flush=True)

    rows_by_url: dict[str, dict] = {}
    for f in partial_files:
        rows = json.loads(f.read_text())
        if not isinstance(rows, list):
            print(f"  WARNING: {f.name} is not a JSON array, skipping", file=sys.stderr)
            continue
        added = 0
        for row in rows:
            url = (row.get("url") or "").strip()
            if url and url not in rows_by_url:
                rows_by_url[url] = row
                added += 1
        print(f"  {f.name}: {len(rows)} rows, {added} new", flush=True)

    merged = list(rows_by_url.values())
    output_file = runs_dir / f"{args.provider}_jobs_live_{args.date}.json"
    output_file.write_text(json.dumps(merged, indent=2, ensure_ascii=False) + "\n")

    print(json.dumps({
        "out": str(output_file),
        "total": len(merged),
        "partial_files": len(partial_files),
        "missing_descriptions": sum(1 for r in merged if not r.get("description")),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
