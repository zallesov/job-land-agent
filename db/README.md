# db/

PocketBase schema, migrations, and the shared type source for the rest of the
monorepo. The database is **remote-only**: a single PocketBase instance at
`https://pb.zall.dev`, backing the Hermes agent, the dashboard, and (soon) the
MCP server. There is no local PocketBase and no staging environment.

```
db/
  pb_migrations/   PocketBase JS migration files (the source of truth for schema)
  schema/types.ts  Generated TS types — shared by dashboard/ and mcp/
  backups/         Timestamped JSON dumps of every app collection + schema snapshot
  package.json     Just the pocketbase-typegen devDependency + a typegen script
  *.py             Legacy one-off migration scripts (SQLite -> PocketBase import)
```

## Migrations

PocketBase's native migration mechanism is `pb_migrations/*.js` files using the
`migrate((app) => { /* up */ }, (app) => { /* down */ })` pattern. The
`pocketbase serve` binary auto-applies any file it hasn't seen yet at startup,
**if the directory is mounted into the container**.

### History / first-mount caveat

This instance ran for months with schema changes applied **live** via the Admin
UI/REST API — it never had a migrations directory. The files currently in
`pb_migrations/` are a **historical record** of the 2026-06-23 cleanup:

- `1750694400_drop_dead_collections.js` — drops `users` and `applications`.
- `1750694401_convert_id_fields_to_relations.js` — converts four ID-string text
  fields to proper `relation` fields.

Because the live schema is **already in the post-migration state**, PocketBase
will, on first mount, treat these files as "never applied" and run them against
the already-current schema. Every operation in them is therefore written
**defensively** (guarded with `findCollectionByNameOrId` checks / try-catch and
desired-state checks) so that replaying them against the current schema no-ops
cleanly instead of erroring. Do not remove these guards.

### Writing a new migration (the going-forward convention)

From now on, **all schema changes go through this directory** — no more ad-hoc
Admin API / Admin UI edits against the live instance. Workflow:

1. Create `pb_migrations/<unix-ts>_<slug>.js`. Use a unix timestamp prefix so
   files sort in apply order (e.g. `date +%s`).
2. Implement both `up` and `down`. Prefer idempotent / defensive code (check
   current state before mutating) so a file is safe even if it gets replayed.
3. Reference collections by name via `app.findCollectionByNameOrId("name")`;
   add fields with `collection.fields.add(new RelationField({...}))` etc., then
   `app.save(collection)`.
4. Regenerate types: `npm run typegen` (see below). Commit the migration **and**
   the regenerated `schema/types.ts` together.
5. Apply to production by restarting the `pocketbase` container with the
   migrations dir mounted (see next section).

PocketBase JSVM migration API reference: https://pocketbase.io/jsvm/

## Applying migrations to production (mount + restart) — NOT YET WIRED UP

The migrations are written and ready, but the docker-compose mount has **not**
been applied — that requires a brief `pocketbase` container restart, which also
bounces `hermes-agent` (it `depends_on` pocketbase `service_healthy`) and
affects the dashboard. This is production-affecting and needs explicit sign-off.

The container runs on the remote server at
`/docker/hermes-workspace-dwys/docker-compose.yml` (service `pocketbase`, image
`ghcr.io/muchobien/pocketbase:latest`). Its binary lives at
`/usr/local/bin/pocketbase`, so PocketBase resolves `pb_migrations` at
`/usr/local/bin/pb_migrations` (mirroring the existing `pb_data` mount at
`/usr/local/bin/pb_data`).

Proposed compose change — add one line to the `pocketbase` service `volumes:`,
pointing at a copy of this repo's `db/pb_migrations` on the host:

```diff
   pocketbase:
     image: ghcr.io/muchobien/pocketbase:latest
     container_name: pocketbase
     restart: unless-stopped
     ports:
       - "127.0.0.1:8090:8090"
     volumes:
       - /opt/pocketbase/pb_data:/usr/local/bin/pb_data
+      - /opt/pocketbase/pb_migrations:/usr/local/bin/pb_migrations
     command: ["serve", "--http=0.0.0.0:8090"]
```

Apply steps (run on the server, after sign-off):

```bash
# 1. copy migrations to the host path the volume points at
mkdir -p /opt/pocketbase/pb_migrations
cp <repo>/db/pb_migrations/*.js /opt/pocketbase/pb_migrations/

# 2. edit the compose file to add the volume line above

# 3. restart just pocketbase; hermes-agent waits for it to be healthy again
cd /docker/hermes-workspace-dwys
docker compose up -d pocketbase
docker compose logs pocketbase | grep -i migrat   # confirm no-op / applied cleanly
```

Because the defensive migrations no-op against the current schema, the first
boot should log them as applied without changing anything.

## Generating types

`schema/types.ts` is generated from the **live** instance with
[`pocketbase-typegen`](https://github.com/patmood/pocketbase-typegen). It is the
shared type source for `dashboard/` and the future `mcp/` server.

```bash
cd db
npm install
# reads POCKETBASE_URL / POCKETBASE_ADMIN_EMAIL / POCKETBASE_ADMIN_PASSWORD from env
npm run typegen
```

Or directly:

```bash
npx pocketbase-typegen --url https://pb.zall.dev \
  --email <admin-email> --password <admin-password> \
  --out schema/types.ts
```

Credentials live in `agent/.env` and `dashboard/.env.local` (not committed).

> Note: `dashboard/lib/db.ts` currently has hand-rolled interfaces (`Job`,
> `JobAssessment`, `CompanyResearch`, `AgentCommand`, `Interview`, ...) that
> duplicate the generated types. They are now redundant with `schema/types.ts`
> and could be migrated to import from here later. Left untouched for now.

## Backups

`backups/<timestamp>/` holds a JSON dump of every app collection plus a schema
snapshot (`_schema.json`, the raw `/api/collections` response). These are
point-in-time exports, not an automated backup system.
