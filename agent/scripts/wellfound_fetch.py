#!/usr/bin/env python3
"""Fetch the current pipeline worklist for a provider from JobLand (via MCP).

Pipeline steps 4 / 7 / 9 all need "give me this provider's jobs in status X" as a
local file for the next step to consume. One tested helper covers all three.

    python3 scripts/wellfound_fetch.py --status new  --out tmp/wellfound/new.json
    python3 scripts/wellfound_fetch.py --status enriched --out tmp/wellfound/enriched.json
    python3 scripts/wellfound_fetch.py --out tmp/wellfound/all.json   # all statuses

All DB access is JobLandMCP-only (scripts.mcp_client). No direct backend client.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from scripts.mcp_client import get_client  # noqa: E402


def _esc(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def build_filter(provider: str, status: str | None) -> str:
    clauses = [f'provider = "{_esc(provider)}"']
    if status:
        clauses.append(f'status = "{_esc(status)}"')
    return " && ".join(clauses)


def fetch_jobs(provider: str = "wellfound", status: str | None = None, client=None) -> list[dict]:
    client = client or get_client()
    return client.list_all_jobs(build_filter(provider, status))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--provider", default="wellfound")
    ap.add_argument("--status", default=None, help="new | enriched | screened | ... (omit for all)")
    ap.add_argument("--out", default=None, help="write JSON list here (else stdout)")
    args = ap.parse_args(argv)

    jobs = fetch_jobs(args.provider, args.status)
    payload = json.dumps(jobs, indent=2, ensure_ascii=False)

    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(payload)
        label = args.status or "any"
        print(f"[fetch] {len(jobs)} {args.provider} jobs (status={label}) -> {out}", flush=True)
    else:
        print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
