# Interviews Project — Claude Directives

## Skills location

**All project skills live in `skills/`.** Never create skills in `hermes-profile/skills/` or `tmp/skills/`.

`hermes-profile/config.yaml` already has `skills.external_dirs: ['../skills']` so both Claude (via Skill tool) and Hermes agent load from the same directory.

## Scripts structure

Provider-specific scrapers: `scripts/providers/<name>/scrape_jobs.py`
Generic pipeline scripts: `scripts/` root (scraping_pipeline.py, db.py, etc.)
**Never create standalone `scrape_<provider>.py` scripts in `scripts/` root.**

All providers run via the unified pipeline:
```
python3 scripts/scraping_pipeline.py --provider <name>
```
