# JobLandAgent — Claude Directives

Part of the `joblandagent` monorepo (`~/joblandagent/`): `agent/` (this dir), `dashboard/`, `db/`, `mcp/`, `scripts/`.
This directory is the agent's working root — all relative paths in skills/scripts resolve from here.

## Skills location

**All project skills live in `skills/`.** Never create skills outside this directory.

## Scripts structure

Provider-specific scrapers: `scripts/providers/<name>/scrape_jobs.py`
Generic pipeline scripts: `scripts/` root (scraping_pipeline.py, pb_client.py, etc.)
**Never create standalone `scrape_<provider>.py` scripts in `scripts/` root.**

All providers run via the unified pipeline:
```
python3 scripts/scraping_pipeline.py --provider <name>
```

## Database

All job data lives in remote PocketBase (`POCKETBASE_URL` in `.env`). Never use sqlite.
DB schema/migration tooling lives in `../db/` (sibling dir), not here — `scripts/pb_client.py`
stays in this repo since pipeline modules import it directly (`from scripts.pb_client import get_pb`).
This will change once the agent talks to PocketBase only through `../mcp/`.

## Dashboard

The dashboard moved to `../dashboard/` — separate dev/deploy cycle, no longer reachable from
agent skills. Do not reintroduce a `run-dashboard` skill here.
