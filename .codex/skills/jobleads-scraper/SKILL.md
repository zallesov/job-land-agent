---
name: jobleads-scraper
description: Knows how to invoke the JobLeads scraper script with location parameters. Use when running the jobleads scraping step of the daily pipeline.
---

# JobLeads Scraper

## Script

```
python3 scripts/scrape_jobleads.py
```

## Parameters

- `--location <preset>` — named preset: `berlin` or `spain`
- `--headless` — always pass this for unattended runs
- `--date <YYYY-MM-DD>` — optional, defaults to today

Note: JobLeads searches are not title-specific (results are "for you" feed filtered by location + salary). No `--titles` parameter.

## Output

Writes partial JSON to:
```
outputs/jobleads/runs/jobleads_jobs_live_<date>_<location_slug>.json
```

## Auth

Browser profile at `~/.interviews-browser-profile` must be pre-authenticated.
If auth fails, script exits with code 1 and prints error to stderr.

## Example Invocations

```bash
python3 scripts/scrape_jobleads.py --location spain --headless

python3 scripts/scrape_jobleads.py --location berlin --headless
```

## Success Check

Exit code 0. Stdout contains JSON with `count` > 0.

## Known Locations

| Preset   | Country | URL Filter |
|----------|---------|------------|
| `spain`  | Spain   | ES, remote, 100k+ |
| `berlin` | Germany | Berlin, remote, 100k+ |
