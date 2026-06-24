# joblandagent

Monorepo for JobLandAgent — split from the original combined `interviews` /
`~/.hermes/profiles/joblandagent-dev` checkout so each piece can ship on its own cycle.

```
agent/        Hermes skills + pipeline scripts + tests. The agent itself.
dashboard/    Next.js dashboard (PocketBase login; pages talk to PocketBase).
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

The host is `72.61.183.105` (`ssh hermes`). Two compose stacks plus traefik:

**Data-plane stack** — `/docker/joblandagent/`, one compose project:

| Service | Container | Image | Public host (via traefik) |
|---|---|---|---|
| `pocketbase` | `pocketbase` | `ghcr.io/muchobien/pocketbase:latest` | `pb.zall.dev` |
| `dashboard` | `joblandagent-dashboard` | `joblandagent-dashboard:latest` (built here) | `jobs.zall.dev` (PocketBase login) |
| `mcp` | `joblandagent-mcp` | `joblandagent-mcp:latest` (built here) | `mcp.zall.dev` (Bearer token) |

Compose source of truth: [`deploy/docker-compose.yml`](deploy/docker-compose.yml)
(env template: [`deploy/.env.example`](deploy/.env.example); the real `.env`
lives only on the host). PocketBase data is host-mounted at
`/opt/pocketbase/{pb_data,pb_migrations}` — survives container/stack recreation.

The dashboard is gated by a real **PocketBase user login** (the `users` auth
collection), not HTTP Basic — see `dashboard/app/login` + `dashboard/lib/auth.ts`.
App collections are locked to `@request.auth.id != ""`. The browser bundle
hard-codes `NEXT_PUBLIC_POCKETBASE_URL` at **build** time (baked by
`deploy-stack.sh` / the Dockerfile `ARG`, default `https://pb.zall.dev`).

**Hermes agent stack** — `/docker/hermes-workspace-dwys/`, its own compose
project (registry images, separate cycle). The agent reaches the DB only via
`https://pb.zall.dev` / the MCP server, so it is deliberately not in the
data-plane stack. Repo copy: [`deploy/hermes-compose.yml`](deploy/hermes-compose.yml)
(env template: [`deploy/hermes.env.example`](deploy/hermes.env.example)). Its
named volumes `hermes-agent-data` and `hermes-workspace-files` hold the agent's
**auth tokens + workspace** — never `down -v` this stack.

`mcp` talks to PocketBase internally (`http://pocketbase:8090`); the dashboard
and agent use the public `https://pb.zall.dev`.

### Deploy

```bash
scripts/deploy-stack.sh    # backup DB -> build dashboard+mcp (amd64) -> ship -> up -d
scripts/deploy-hermes.sh   # ship hermes compose -> pull images -> up -d (volumes kept)
scripts/migrate-db.sh      # ship db/pb_migrations/*.js -> restart pocketbase to apply
```

On a **fresh** PocketBase, seed the dashboard login user + lock the app
collections (idempotent):

```bash
ADMIN_EMAIL=you@example.com ADMIN_PASSWORD=... python3 agent/scripts/seed_dashboard_user.py
```

### Verify

```bash
curl -s  https://pb.zall.dev/api/health         # {"code":200,...}
curl -sI https://jobs.zall.dev                  # 307 -> /login (PocketBase login)
curl -s  https://jobs.zall.dev/api/jobs         # {"error":"Unauthorized"} when logged out
curl -s  https://mcp.zall.dev/healthz           # {"ok":true}
curl -sI https://hermes.zall.dev/login          # 200 (Hermes dashboard)
ssh hermes 'cd /docker/joblandagent && docker compose ps'
ssh hermes 'cd /docker/hermes-workspace-dwys && docker compose ps'
```

## Status

- `agent/` and `dashboard/` extracted from the combined profile checkout (2026-06-23).
- `db/` has migrations + generated types (2026-06-23 cleanup: dropped dead
  `users`/`applications` collections, cleaned up 646 orphaned `job_assessments`,
  converted FK-ish text fields to proper `relation` fields). Mount + restart to
  actually apply the migration runner on the server is still pending sign-off.
- `mcp/` contains the HTTP MCP server for remote Hermes access to PocketBase
  `jobs` and `interviews` data.
