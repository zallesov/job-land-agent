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

## Applying migrations to production (mount + restart)

**Wired up as of 2026-06-23.** The `pocketbase` service on the server
(`/docker/hermes-workspace-dwys/docker-compose.yml`, image
`ghcr.io/muchobien/pocketbase:latest`) now mounts the migrations dir:

```yaml
    volumes:
      - /opt/pocketbase/pb_data:/usr/local/bin/pb_data
      - /opt/pocketbase/pb_migrations:/usr/local/bin/pb_migrations
```

(mirrors the `pb_data` mount — PocketBase resolves `pb_migrations` as a sibling
of its binary dir, `/usr/local/bin/`). The two historical migrations in this
repo have been applied (no-op, since the schema was already in that state).

Going forward, use `scripts/migrate-db.sh` from the repo root:

```bash
scripts/migrate-db.sh
```

It copies `db/pb_migrations/*.js` to `hermes:/opt/pocketbase/pb_migrations/`
(safe, no restart yet), then asks for interactive confirmation before
restarting `pocketbase` to actually apply them. Restarting briefly bounces
`hermes-agent` (`depends_on` pocketbase `service_healthy`) and the dashboard —
a few seconds of DB downtime. Run it from an actual terminal (the confirmation
prompt needs a real human at the keyboard, not a piped/automated "y").

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
