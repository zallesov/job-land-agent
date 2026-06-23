# joblandagent

Monorepo for JobLandAgent — split from the original combined `interviews` /
`~/.hermes/profiles/joblandagent-dev` checkout so each piece can ship on its own cycle.

```
agent/        Hermes skills + pipeline scripts + tests. The agent itself.
dashboard/    Next.js dashboard (Pages talk to PocketBase directly today).
db/           PocketBase migration/schema tooling (one-off scripts, no client lib).
mcp/          MCP server exposing job data to the agent — not built yet.
scripts/      Dev-only one-off scripts. Not used by the agent at runtime.
```

## Database

PocketBase, remote: `pb.zall.dev`. No local instance. Credentials in `agent/.env`
(`POCKETBASE_URL`, `POCKETBASE_ADMIN_EMAIL`, `POCKETBASE_ADMIN_PASSWORD`) — not committed.

## Running the agent

The agent still runs as a Hermes profile at `~/.hermes/profiles/joblandagent-dev` — this repo
is the clean dev checkout. See `agent/AGENTS.md` and `agent/CLAUDE.md` for pipeline/skill details.

## Running the dashboard

```bash
cd dashboard
npm install
npm run dev   # http://localhost:3000
```

## Status

- `agent/` and `dashboard/` extracted from the combined profile checkout (2026-06-23).
- `db/` and `mcp/` are placeholders — no PocketBase docker/schema files exist yet (DB is
  remote-only); MCP server work hasn't started.
