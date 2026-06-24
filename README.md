# joblandagent

Monorepo for JobLandAgent — split from the original combined `interviews` /
`~/.hermes/profiles/joblandagent-dev` checkout so each piece can ship on its own cycle.

```
agent/        Hermes skills + pipeline scripts + tests. The agent itself.
dashboard/    Next.js dashboard (Pages talk to PocketBase directly today).
db/           PocketBase migrations + generated types (db/README.md). Shared schema source.
mcp/          HTTP MCP server exposing PocketBase job/interview data to Hermes.
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

## Deployment (production)

All three data-plane apps run in **one** compose stack on the hermes host
(`72.61.183.105`, `ssh hermes`) at `/docker/joblandagent/`:

| Service | Container | Image | Public host (via traefik) |
|---|---|---|---|
| `pocketbase` | `pocketbase` | `ghcr.io/muchobien/pocketbase:latest` | `pb.zall.dev` |
| `dashboard` | `joblandagent-dashboard` | `joblandagent-dashboard:latest` (built here) | `jobs.zall.dev` (HTTP Basic) |
| `mcp` | `joblandagent-mcp` | `joblandagent-mcp:latest` (built here) | `mcp.zall.dev` (Bearer token) |

Compose source of truth: [`deploy/docker-compose.yml`](deploy/docker-compose.yml)
(env template: [`deploy/.env.example`](deploy/.env.example); the real `.env`
lives only on the host). PocketBase data is host-mounted at
`/opt/pocketbase/{pb_data,pb_migrations}` — survives container/stack recreation.

The **Hermes agent** runs in its own stack (`/docker/hermes-workspace-dwys/`)
and reaches the DB only through the MCP server, so it is deliberately not part
of this stack. `mcp` talks to PocketBase internally (`http://pocketbase:8090`);
the dashboard uses the public `https://pb.zall.dev`.

### Deploy

```bash
scripts/deploy-stack.sh    # backup DB -> build dashboard+mcp (amd64) -> ship -> up -d
```

### Verify

```bash
curl -s  https://pb.zall.dev/api/health         # {"code":200,...}
curl -sI https://jobs.zall.dev                  # 401 unauthenticated (Basic), 200 with creds
curl -s  https://mcp.zall.dev/healthz           # {"ok":true}
ssh hermes 'cd /docker/joblandagent && docker compose ps'
```

## Status

- `agent/` and `dashboard/` extracted from the combined profile checkout (2026-06-23).
- `db/` has migrations + generated types (2026-06-23 cleanup: dropped dead
  `users`/`applications` collections, cleaned up 646 orphaned `job_assessments`,
  converted FK-ish text fields to proper `relation` fields). Mount + restart to
  actually apply the migration runner on the server is still pending sign-off.
- `mcp/` contains the HTTP MCP server for remote Hermes access to PocketBase
  `jobs` and `interviews` data.
