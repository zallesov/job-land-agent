# Hermes Custom Image Deployment Design

## Context

JobLandAgent currently deploys two separate stacks on the `hermes` host:

- The data-plane stack in `/docker/joblandagent/`, with locally built
  `joblandagent-dashboard:latest` and `joblandagent-mcp:latest` images plus
  PocketBase.
- The Hermes stack in `/docker/hermes-workspace-dwys/`, with upstream images
  `nousresearch/hermes-agent:latest` and
  `ghcr.io/outsourc-e/hermes-workspace:latest`.

The Hermes profile currently lives under the persistent `/opt/data` volume. That
means runtime state and deployable profile files are mixed together. The new
deployment should make the Docker image the source of truth for JobLandAgent
profile code while keeping Hermes runtime state persistent.

## Goals

- Build a local custom Hermes agent image, `joblandagent-hermes-agent:latest`.
- Keep Hermes agent runtime state in the existing `/opt/data` volume.
- Store JobLandAgent distributable profile files in the image.
- On container start, synchronize only `distribution_owned` files from the image
  into `/opt/data/profiles/joblandagent`.
- Preserve secrets, auth, user configuration, state databases, logs, sessions,
  memories, cron data, and caches across deploys.
- Keep the existing separate-container architecture unless a concrete need for a
  second custom Hermes image appears.

## Non-Goals

- Do not merge Hermes agent, Hermes workspace, dashboard, MCP, and PocketBase
  into one container.
- Do not bake secrets into any image.
- Do not remove the `/opt/data` volume.
- Do not use the persistent volume as the primary delivery mechanism for skills,
  scripts, or base profile config.
- Do not change the JobLandAgent dashboard and MCP data-plane deployment beyond
  integration points needed by Hermes.

## Architecture

The Hermes stack should keep two services:

- `hermes-agent`: uses the new `joblandagent-hermes-agent:latest` image.
- `hermes-workspace`: continues using
  `ghcr.io/outsourc-e/hermes-workspace:latest` unless workspace customization is
  needed later.

The data-plane stack remains separate:

- `pocketbase`
- `joblandagent-dashboard:latest`
- `joblandagent-mcp:latest`

The custom Hermes agent image is built from `nousresearch/hermes-agent:latest`.
It contains a profile template, for example:

```text
/opt/joblandagent/profile-template/
```

At startup, a bootstrap script syncs the template into:

```text
/opt/data/profiles/joblandagent/
```

The sync set is read from `agent/distribution.yaml` `distribution_owned`. Files
outside that list are treated as runtime or user-owned and are not overwritten.
Implementation must update `distribution_owned` before enabling bootstrap sync
so every intended image-owned file is explicitly listed.

## Image Contents

The custom image should include the JobLandAgent profile distribution files,
including:

- `distribution.yaml`
- `SOUL.md`
- `AGENTS.md`
- `CLAUDE.md` if it remains part of the profile contract
- `config.yaml`
- `.env.EXAMPLE`
- `package.json`
- lockfiles and workspace manifests used by the profile
- `requirements.txt`
- `start-chrome.sh`
- `config/`
- `skills/`
- `scripts/`
- `dashboard/` if it remains listed as distribution-owned
- `mcp.json`

Before implementation is considered complete, `agent/distribution.yaml`
`distribution_owned` must include every file or directory the bootstrap is
expected to sync. In particular, `mcp.json` must be added there, and
`AGENTS.md` / `CLAUDE.md` should be listed if they remain part of the installed
profile contract.

The image may also install deterministic runtime dependencies if needed, but
that decision should be made during implementation after inspecting current
profile commands and Hermes base-image capabilities.

## Volume Ownership

The `/opt/data` volume remains required. It owns mutable Hermes state, including:

- profile `.env`
- provider and service auth tokens
- sessions and history
- state databases
- logs
- memories
- cron data
- caches
- `config/user.yaml`
- runtime-generated profile files

The bootstrap must not delete or overwrite those files.

The `hermes-workspace-files` volume appears less critical because `/workspace`
is currently empty on the host. It can remain initially to avoid behavioral
change. Removing it can be a later cleanup after verifying Hermes workspace does
not rely on persistent workspace files.

## Startup Sync Behavior

On every container start:

1. Ensure `/opt/data/profiles/joblandagent` exists.
2. Read `distribution_owned` from the image's `distribution.yaml`.
3. Copy each listed file or directory from the image template into the profile.
4. Do not copy files that are not listed in `distribution_owned`, except for
   explicit deployment metadata such as a sync stamp.
5. Ensure resulting files are owned by the Hermes runtime user.
6. Continue to the normal Hermes command, currently `gateway run`.

The sync happens every start, not only on first install. This ensures a new
Docker image actually updates skills, scripts, and base profile files in an
existing persistent profile.

The implementation should avoid deleting unknown runtime files. If a
distribution-owned directory is copied, the implementation should decide
carefully whether to mirror-delete removed files or only overlay-copy. The
safer first implementation is overlay-copy without deleting unknown files.

## MCP Configuration

The image should include `agent/mcp.json` as part of the profile distribution.
The bootstrap or a small helper should merge it into the active profile
`config.yaml` as `mcp_servers.jobland`.

The secret `MCP_JOBLAND_API_KEY` must remain runtime-provided through compose
`.env` or the profile `.env`. It must not be baked into the image.

The current post-deploy MCP merge script can either be removed or reduced to
secret validation once the image bootstrap owns the non-secret MCP server
configuration.

## Compose And Deploy Flow

`deploy/hermes-compose.yml` should change `hermes-agent.image` from the upstream
image to:

```text
joblandagent-hermes-agent:latest
```

The deploy script should mirror the existing dashboard/MCP deploy pattern:

1. Build `joblandagent-hermes-agent:latest` locally for `linux/amd64`.
2. Ship it to the `hermes` host with `docker save | ssh docker load`.
3. Stage `deploy/hermes-compose.yml`.
4. Validate compose on the host.
5. Run `docker compose up -d`.
6. Check service status and validate that Hermes dashboard/API are reachable.

The deploy should not run `docker compose down -v`.

## Testing

Implementation should include focused local validation:

- Build the custom image.
- Run the bootstrap against a temporary profile directory.
- Verify `distribution_owned` files are copied.
- Verify runtime files such as `.env`, `config/user.yaml`, `state.db`, logs, and
  auth-like files are preserved.
- Validate compose config.

Deployment validation on the server should check:

- `docker compose ps` for Hermes stack.
- Hermes agent uses `joblandagent-hermes-agent:latest`.
- `/opt/data/profiles/joblandagent` contains updated distribution files.
- Existing runtime files remain present.
- Hermes dashboard and API remain enabled.
- JobLand MCP config exists and uses the runtime API key placeholder.

## Risks

- If bootstrap overwrites runtime files, auth and user state can be lost.
- If bootstrap only runs on first install, image deploys will not update the
  active profile.
- If `/opt/data` volume is removed, Hermes runtime state will be lost.
- If secrets are copied into the image, deploy artifacts become unsafe.
- If directory sync semantics are too aggressive, removed distribution files may
  delete user-created files. Start with conservative overlay sync.
