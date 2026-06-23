# joblandagent

Monorepo for JobLandAgent — split from the original combined `interviews` /
`~/.hermes/profiles/joblandagent-dev` checkout so each piece can ship on its own cycle.

```
agent/        Hermes skills + pipeline scripts + tests. The agent itself.
dashboard/    Next.js dashboard (Pages talk to PocketBase directly today).
db/           PocketBase migrations + generated types (db/README.md). Shared schema source.
mcp/          MCP server exposing job data to the agent — not built yet.
scripts/      Dev-only one-off scripts. Not used by the agent at runtime.
```

## Database

PocketBase, remote: `pb.zall.dev`. No local instance. Credentials in `agent/.env`
(`POCKETBASE_URL`, `POCKETBASE_ADMIN_EMAIL`, `POCKETBASE_ADMIN_PASSWORD`) — not committed.

## Running the agent

The agent still runs as a Hermes profile at `~/.hermes/profiles/joblandagent-dev` — this repo
is the clean dev checkout. See `agent/AGENTS.md` and `agent/CLAUDE.md` for pipeline/skill details.

## Database migrations

Schema lives in `db/pb_migrations/` (PocketBase JS migrations) — no more ad-hoc
schema edits via the Admin UI/API. Full procedure, conventions, and the
first-mount caveat are in `db/README.md`. Quick version:

1. Write `db/pb_migrations/<unix-ts>_<slug>.js` (defensive: guard against the
   change already being applied).
2. `cd db && npm run typegen` — regenerate `schema/types.ts` from the live
   instance, commit it alongside the migration.
3. `scripts/migrate-db.sh` — ships the `.js` files to the server and, after you
   confirm interactively, restarts the `pocketbase` container so it picks them
   up. This briefly bounces `hermes-agent` and the dashboard (a few seconds).

There's a single PocketBase instance (`pb.zall.dev`), no staging — every
migration runs straight against production.

## Running the dashboard

```bash
cd dashboard
npm install
npm run dev   # http://localhost:3000
```

## Status

- `agent/` and `dashboard/` extracted from the combined profile checkout (2026-06-23).
- `db/` has migrations + generated types (2026-06-23 cleanup: dropped dead
  `users`/`applications` collections, cleaned up 646 orphaned `job_assessments`,
  converted FK-ish text fields to proper `relation` fields). Mount + restart to
  actually apply the migration runner on the server is still pending sign-off.
- `mcp/` is a placeholder — work hasn't started.
