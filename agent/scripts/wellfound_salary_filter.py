#!/usr/bin/env python3
"""
Primary salary filter — run BEFORE enrichment to cut clearly-underpaid roles.

Reads the scraped feed (wellfound_scrape.sh output) and the candidate's
`desired_salary` from config/user.yaml. Splits jobs into a shortlist (passes the
salary floor, or salary unknown) and a dropped list (max comp clearly below floor).

Coarse on purpose: it only looks at the salary string already on the feed card. It does
NOT convert currencies (a €/$/£ k-number is compared directly to the floor) and it keeps
anything with no salary shown — enrichment resolves those. The goal is to shrink the
enrichment batch, not to make the final apply/skip decision.

Usage:
  python3 scripts/wellfound_salary_filter.py [jobs.json] [--config config/user.yaml] \
          [--out-dir tmp/wellfound] [--floor 100000]

Outputs (in --out-dir):
  shortlist.json   jobs to enrich (pass + unknown)
  dropped.json     jobs cut for low pay (audit trail)
"""
import argparse, json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]      # profile root (parent of scripts/)
def under_root(rel):
    return str(ROOT / rel)


def parse_floor_from_config(config_path: Path):
    """Pull desired_salary from user.yaml without a yaml dependency."""
    if not config_path.exists():
        return None
    for line in config_path.read_text().splitlines():
        if line.strip().startswith("desired_salary:"):
            raw = line.split(":", 1)[1].strip().strip('"').strip("'")
            return salary_to_number(raw)
    return None


def salary_to_number(text):
    """Largest monetary figure in a string -> absolute number. '€100,000'->100000,
    '$140k'->140000, '€54k – €120k'->120000, '$150k+'->150000. None if no figure."""
    if not text:
        return None
    # drop equity/percentage tokens first ("3.0% – 5.0%", "0.5%") so they are not read as pay
    text = re.sub(r"\d[\d,]*\.?\d*\s*%", " ", text)
    vals = []
    # match 120k / 120K / 100,000 / 100000  (optional k = thousands)
    for m in re.finditer(r"(\d[\d,]*\.?\d*)\s*([kK])?", text):
        num = m.group(1).replace(",", "")
        if not num or num == ".":
            continue
        try:
            v = float(num)
        except ValueError:
            continue
        if m.group(2):              # explicit k
            v *= 1000
        elif v < 1000:              # bare "120" in a salary context => 120k
            v *= 1000
        if v >= 1000:               # ignore stray small numbers (percentages, etc.)
            vals.append(v)
    return max(vals) if vals else None


def classify(job, floor):
    # prefer the parsed range, fall back to the raw compensation string
    comp = job.get("salary") or job.get("compensation") or ""
    max_comp = salary_to_number(comp)
    if max_comp is None:
        return "unknown", None
    return ("pass" if max_comp >= floor else "drop_low"), max_comp


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("jobs", nargs="?", default=under_root("tmp/wellfound/jobs.json"))
    ap.add_argument("--config", default=under_root("config/user.yaml"))
    ap.add_argument("--out-dir", default=under_root("tmp/wellfound"))
    ap.add_argument("--floor", type=float, default=None,
                    help="Override salary floor (absolute, e.g. 100000)")
    args = ap.parse_args()

    floor = args.floor or parse_floor_from_config(Path(args.config))
    if not floor:
        print("No salary floor (set desired_salary in user.yaml or pass --floor)", file=sys.stderr)
        sys.exit(1)

    data = json.loads(Path(args.jobs).read_text())
    jobs = data.get("jobs", data if isinstance(data, list) else [])

    shortlist, dropped = [], []
    for j in jobs:
        verdict, max_comp = classify(j, floor)
        j = {**j, "salary_max_parsed": max_comp, "salary_verdict": verdict}
        (dropped if verdict == "drop_low" else shortlist).append(j)

    out = Path(args.out_dir)
    short_path = out / "shortlist.json"
    drop_path = out / "dropped.json"
    short_path.write_text(json.dumps(
        {"floor": floor, "count": len(shortlist), "jobs": shortlist}, indent=2, ensure_ascii=False))
    drop_path.write_text(json.dumps(
        {"floor": floor, "count": len(dropped), "jobs": dropped}, indent=2, ensure_ascii=False))

    n_pass = sum(1 for j in shortlist if j["salary_verdict"] == "pass")
    n_unknown = sum(1 for j in shortlist if j["salary_verdict"] == "unknown")
    print(f"floor: {floor:,.0f}")
    print(f"total:    {len(jobs)}")
    print(f"shortlist: {len(shortlist)}  (pass={n_pass}, unknown={n_unknown})  -> {short_path}")
    print(f"dropped:   {len(dropped)}  (below floor)               -> {drop_path}")


if __name__ == "__main__":
    main()
