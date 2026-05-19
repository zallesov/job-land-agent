---
name: greenhouse-scraper
description: Knows how to invoke the Greenhouse scraper script with location and title parameters. Use when running the greenhouse scraping step of the daily pipeline.
---

# Greenhouse Scraper

## Script

```
python3 scripts/scrape_greenhouse.py
```

## Parameters

- `--location <preset>` — named preset: `berlin` or `spain`
- `--titles <title1> <title2> ...` — one or more job title strings
- `--headless` — always pass this for unattended runs
- `--date <YYYY-MM-DD>` — optional, defaults to today

## Output

Writes partial JSON to:
```
outputs/greenhouse/runs/greenhouse_jobs_live_<date>_<location_slug>.json
```

## Auth

Browser profile at `~/.interviews-browser-profile` must be pre-authenticated.
If auth fails (no `--wait-auth` flag), script exits with code 1 and prints error to stderr.

## Example Invocations

```bash
python3 scripts/scrape_greenhouse.py \
  --location berlin \
  --titles "Software Engineer" "AI Engineer" "Engineering Manager" \
  --headless

python3 scripts/scrape_greenhouse.py \
  --location spain \
  --titles "Software Engineer" \
  --headless
```

## Success Check

Exit code 0. Stdout contains JSON with `count` > 0.

## Known Locations

| Preset   | Country |
|----------|---------|
| `berlin` | Germany |
| `spain`  | Spain   |
