#!/usr/bin/env python3
"""
Wellfound preflight — fail fast before doing real work.

Checks the local browser runtime and required files. Does NOT check JobLandMCP write
tools (that is the agent's job — MCP is not reachable from a plain script); the preflight
skill reminds the agent to verify those separately.

Exit 0 = all good. Exit 1 = something needs fixing (details printed).

Usage:  python3 scripts/wellfound_preflight.py
"""
import json, os, sys, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]          # profile root (parent of scripts/)
CDP = "http://127.0.0.1:9222"


def check(name, ok, detail=""):
    print(f"  [{'OK ' if ok else 'FAIL'}] {name}{' — ' + detail if detail else ''}")
    return ok


def cdp_version():
    try:
        with urllib.request.urlopen(f"{CDP}/json/version", timeout=5) as r:
            return json.load(r)
    except Exception:
        return None


def main():
    ok = True
    print("Wellfound preflight:")

    # 1. Chrome on 9222
    ver = cdp_version()
    ok &= check("Chrome CDP on 9222", ver is not None,
                "" if ver else "not reachable — run: bash start-chrome.sh")

    # 2. Headed, not HeadlessChrome
    if ver:
        ua = ver.get("User-Agent", "")
        ok &= check("Browser is headed (not HeadlessChrome)", "Headless" not in ua,
                    ua[:60] if "Headless" in ua else ver.get("Browser", ""))

    # 3. Required scripts/files exist at profile root
    needed = ["scripts/wellfound_scrape.sh", "scripts/wellfound_salary_filter.py",
              "scripts/dedup_jobs.py", "scripts/wellfound_enrich.py",
              "scripts/load_session.py", "start-chrome.sh", "config/user.yaml"]
    for rel in needed:
        ok &= check(f"exists {rel}", (ROOT / rel).exists())

    # 4. tmp/wellfound writable
    tmp = ROOT / "tmp" / "wellfound"
    try:
        tmp.mkdir(parents=True, exist_ok=True)
        (tmp / ".writetest").write_text("x"); (tmp / ".writetest").unlink()
        ok &= check("tmp/wellfound writable", True, str(tmp))
    except Exception as e:
        ok &= check("tmp/wellfound writable", False, str(e)[:80])

    # 5. salary floor configured
    cfg = ROOT / "config" / "user.yaml"
    floor = any(l.strip().startswith("desired_salary:") for l in cfg.read_text().splitlines()) if cfg.exists() else False
    ok &= check("desired_salary set in config/user.yaml", floor)

    print()
    if ok:
        print("preflight OK. Wellfound session liveness + JobLandMCP write tools: "
              "verify via wellfound-check-auth and an MCP tool list (agent-side).")
    else:
        print("preflight FAILED — fix the items above before running the flow.", file=sys.stderr)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
