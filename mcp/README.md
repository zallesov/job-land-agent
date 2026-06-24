# JobLandAgent MCP Server

HTTP MCP server for privileged access to JobLandAgent PocketBase collections.
Hermes connects to this service instead of receiving PocketBase credentials.

## Environment

```bash
export POCKETBASE_URL="https://pb.zall.dev"
export POCKETBASE_ADMIN_EMAIL="..."
export POCKETBASE_ADMIN_PASSWORD="..."
export MCP_API_TOKEN="bootstrap-token"
export PORT=8787
```

`MCP_API_TOKEN` is a bootstrap full-access bearer token. Additional tokens can
be stored in the PocketBase `mcp_tokens` collection as SHA-256 hashes.

Create a token hash:

```bash
printf '%s' '<token>' | shasum -a 256
```

Apply `../db/pb_migrations/1782297600_create_mcp_tokens.js` before relying on
database-backed tokens. After applying migrations, regenerate
`../db/schema/types.ts` with the normal `db npm run typegen` workflow.

Token scopes:

- `jobs:*`
- `jobs:read`
- `jobs:write`
- `interviews:*`
- `interviews:read`
- `interviews:write`

## Run

```bash
npm install
npm run dev
```

Health check:

```bash
curl http://127.0.0.1:8787/healthz
```

## Docker

Build locally for the x86_64 Hermes host:

```bash
docker buildx build --platform linux/amd64 --load -t joblandagent-mcp:latest .
```

Ship without a registry:

```bash
docker save joblandagent-mcp:latest | ssh hermes 'docker load'
```

The container listens on `PORT` (default `8787`) and should run behind the
server reverse proxy with TLS.

Hermes config:

```yaml
mcp_servers:
  jobland:
    url: "https://mcp-jobland.example.com/mcp"
    headers:
      Authorization: "Bearer <token>"
```

## Tools

- `jobs_list`, `jobs_get`, `jobs_create`, `jobs_update`, `jobs_delete`
- `jobs_find_by_url`, `jobs_search`
- `interviews_list`, `interviews_get`, `interviews_create`
- `interviews_update`, `interviews_delete`, `interviews_search`

`jobs_delete` is a soft delete: it sets `deleted_at` and `updated_at`.
`interviews_delete` hard-deletes the interview record.
