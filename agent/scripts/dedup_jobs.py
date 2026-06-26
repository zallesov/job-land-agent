#!/usr/bin/env python3
"""
Generic, provider-agnostic job dedup. One script for every provider.

Drops jobs already tracked in JobLand (and duplicates within the same batch) by matching
on any of three keys — the same signals the legacy pipeline used, plus apply_url:

  - dedup_key  = "{company}::{title}"   (cross-provider: the SAME role re-posted on
                  another site has the same company+title even with a different URL)
  - apply_url  (normalized)             (cross-provider: same ATS application link)
  - url        (normalized)             (same-provider: the exact posting)

A job is a duplicate if ANY of its available keys is already tracked OR already seen
earlier in this batch. Jobs only carry the keys they have at the current stage:
  - pre-enrich feed jobs usually have only `url`  -> same-provider dedup
  - post-enrich jobs have company+title+apply_url -> cross-provider dedup
so the same script is run twice in a flow (before and after enrichment).

This script does NOT read JobLand. The agent fetches the tracked keys via JobLandMCP and
writes them to --existing (see the `dedup-jobs` skill). This keeps the JobLand-only-via-MCP
boundary while sharing one dedup implementation.

--existing accepts either:
  A) a structured dict: {"dedup_keys": [...], "urls": [...], "apply_urls": [...]}
  B) a list of job objects (uses their company/title/url/apply_url fields)
  C) a plain-text file, one URL per line

Usage:
  python3 scripts/dedup_jobs.py IN.json --existing tracked.json \
      --out new.json --skipped skipped.json [--by dedup_key,apply_url,url]
"""
import argparse, json, re, sys
from pathlib import Path

JOB_ID = re.compile(r"/jobs/(\d+)")
ROOT = Path(__file__).resolve().parents[1]      # profile root (parent of scripts/)
def under_root(rel):
    return str(ROOT / rel)


def norm_url(u):
    if not u:
        return None
    m = JOB_ID.search(u)
    if m:
        return "wf:" + m.group(1)                       # wellfound canonical id
    n = re.sub(r"^https?://", "", u.strip()).split("?")[0].split("#")[0].rstrip("/").lower()
    return n or None


def norm_dk(company, title):
    if not company or not title:
        return None
    return f"{company.strip()}::{title.strip()}".casefold()


def job_keys(j, fields):
    """Yield (kind, value) keys this job carries, limited to `fields`."""
    if "dedup_key" in fields:
        dk = j.get("dedup_key")
        v = dk.casefold() if dk else norm_dk(j.get("company"), j.get("title"))
        if v:
            yield "dedup_key", v
    if "apply_url" in fields:
        v = norm_url(j.get("apply_url"))
        if v:
            yield "apply_url", v
    if "url" in fields:
        v = norm_url(j.get("url"))
        if v:
            yield "url", v


def load_existing(path: Path, fields):
    """Return {kind: set(values)} of already-tracked keys."""
    sets = {"dedup_key": set(), "apply_url": set(), "url": set()}
    raw = path.read_text().strip()
    if not raw:
        return sets
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:                         # plain text URLs
        for line in raw.splitlines():
            v = norm_url(line.strip())
            if v:
                sets["url"].add(v)
        return sets

    if isinstance(data, dict) and ("dedup_keys" in data or "urls" in data or "apply_urls" in data):
        for dk in data.get("dedup_keys", []):
            if dk:
                sets["dedup_key"].add(dk.casefold())
        for u in data.get("urls", []):
            v = norm_url(u)
            if v:
                sets["url"].add(v)
        for u in data.get("apply_urls", []):
            v = norm_url(u)
            if v:
                sets["apply_url"].add(v)
    else:                                                # list of job objects
        items = data.get("jobs", data) if isinstance(data, dict) else data
        for it in items:
            if isinstance(it, str):
                v = norm_url(it)
                if v:
                    sets["url"].add(v)
                continue
            for kind, val in job_keys(it, fields):
                sets[kind].add(val)
    return sets


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input", nargs="?", default=under_root("tmp/wellfound/shortlist.json"))
    ap.add_argument("--existing", default=under_root("tmp/wellfound/tracked.json"),
                    help="Tracked keys from JobLand (filled by the agent via MCP)")
    ap.add_argument("--out", default=under_root("tmp/wellfound/shortlist_new.json"))
    ap.add_argument("--skipped", default=under_root("tmp/wellfound/dedup_skipped.json"))
    ap.add_argument("--by", default="dedup_key,apply_url,url",
                    help="Comma list of match keys to use (default all three)")
    args = ap.parse_args()

    fields = {f.strip() for f in args.by.split(",") if f.strip()}
    existing = load_existing(Path(args.existing), fields)

    data = json.loads(Path(args.input).read_text())
    jobs = data.get("jobs", []) if isinstance(data, dict) else data

    seen = {"dedup_key": set(), "apply_url": set(), "url": set()}
    new, skipped = [], []
    for j in jobs:
        keys = list(job_keys(j, fields))
        dup_kind = next((k for k, v in keys if v in existing[k] or v in seen[k]), None)
        if dup_kind:
            skipped.append({**j, "dedup_reason": dup_kind})
        else:
            for k, v in keys:
                seen[k].add(v)
            new.append(j)

    Path(args.out).write_text(json.dumps({"count": len(new), "jobs": new}, indent=2, ensure_ascii=False))
    Path(args.skipped).write_text(json.dumps({"count": len(skipped), "jobs": skipped}, indent=2, ensure_ascii=False))

    tracked = sum(len(s) for s in existing.values())
    print(f"match keys: {sorted(fields)}")
    print(f"tracked keys: {tracked}")
    print(f"input: {len(jobs)}")
    print(f"new: {len(new)}  -> {args.out}")
    print(f"duplicate (skipped): {len(skipped)}  -> {args.skipped}")


if __name__ == "__main__":
    main()
