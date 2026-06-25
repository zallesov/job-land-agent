# Hermes Custom Image Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and deploy a custom Hermes agent image that owns JobLandAgent distribution files while preserving Hermes runtime state in the existing volume.

**Architecture:** Add a profile bootstrap script and Dockerfile for `joblandagent-hermes-agent:latest`. The container syncs only `distribution_owned` files from an image template into `/opt/data/profiles/joblandagent` before running the normal Hermes gateway command. Compose and deploy scripts switch Hermes agent from an upstream pulled image to a locally built and shipped image.

**Tech Stack:** Bash, Python 3 standard library plus PyYAML from the Hermes base image, Docker buildx, Docker Compose.

---

### Task 1: Add Bootstrap Sync Tests

**Files:**
- Create: `tests/test_hermes_profile_bootstrap.py`
- Create: `docker/hermes-agent/bootstrap-profile.py`

- [ ] **Step 1: Create failing tests for distribution-only sync**

Create `tests/test_hermes_profile_bootstrap.py` with tests that import the bootstrap script by path. The tests should create a temporary template profile containing `distribution.yaml`, `config.yaml`, `mcp.json`, and `scripts/tool.py`; create a runtime profile containing `.env`, `config/user.yaml`, `state.db`, and `logs/agent.log`; run `sync_profile`; and assert distribution files update while runtime files remain unchanged.

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_hermes_profile_bootstrap.py -v`

Expected: FAIL because `docker/hermes-agent/bootstrap-profile.py` does not exist yet.

### Task 2: Implement Bootstrap Sync

**Files:**
- Create: `docker/hermes-agent/bootstrap-profile.py`
- Create: `docker/hermes-agent/entrypoint.sh`
- Test: `tests/test_hermes_profile_bootstrap.py`

- [ ] **Step 1: Implement `bootstrap-profile.py`**

Implement functions:

- `load_distribution_owned(template_dir: Path) -> list[str]`
- `copy_distribution_entry(template_dir: Path, profile_dir: Path, entry: str) -> None`
- `merge_mcp_config(profile_dir: Path, mcp_json_path: Path) -> None`
- `sync_profile(template_dir: Path, profile_dir: Path) -> None`
- `main() -> None`

The copy behavior should overlay files/directories listed in `distribution_owned` and should not delete unknown files from existing directories. `merge_mcp_config` should merge `mcp.json` into `config.yaml` under `mcp_servers`.

- [ ] **Step 2: Implement `entrypoint.sh`**

Create a shell wrapper that runs:

```bash
python /opt/joblandagent/bootstrap-profile.py
exec /init /opt/hermes/docker/entrypoint.sh "$@"
```

If the upstream image's runtime entrypoint differs after inspection, adjust this wrapper to preserve the original command path.

- [ ] **Step 3: Run tests**

Run: `pytest tests/test_hermes_profile_bootstrap.py -v`

Expected: PASS.

### Task 3: Add Custom Hermes Dockerfile

**Files:**
- Create: `docker/hermes-agent/Dockerfile`
- Modify: `.dockerignore` if needed

- [ ] **Step 1: Create Dockerfile**

Create a Dockerfile based on `nousresearch/hermes-agent:latest` that copies:

- `agent/` to `/opt/joblandagent/profile-template/`
- `docker/hermes-agent/bootstrap-profile.py` to `/opt/joblandagent/bootstrap-profile.py`
- `docker/hermes-agent/entrypoint.sh` to `/opt/joblandagent/entrypoint.sh`

Set executable permissions on the entrypoint and configure:

```dockerfile
ENTRYPOINT ["/opt/joblandagent/entrypoint.sh"]
CMD ["gateway", "run"]
```

- [ ] **Step 2: Build image locally**

Run: `docker buildx build --platform linux/amd64 -t joblandagent-hermes-agent:latest --load -f docker/hermes-agent/Dockerfile .`

Expected: image builds successfully.

### Task 4: Update Distribution Metadata

**Files:**
- Modify: `agent/distribution.yaml`

- [ ] **Step 1: Add image-owned files to `distribution_owned`**

Ensure `distribution_owned` includes:

- `AGENTS.md`
- `CLAUDE.md`
- `mcp.json`

Keep existing entries for `skills`, `scripts`, `config`, `dashboard`, and profile manifests.

- [ ] **Step 2: Run bootstrap tests**

Run: `pytest tests/test_hermes_profile_bootstrap.py -v`

Expected: PASS.

### Task 5: Update Hermes Compose And Deploy Script

**Files:**
- Modify: `deploy/hermes-compose.yml`
- Modify: `scripts/deploy-hermes.sh`

- [ ] **Step 1: Update compose image**

Change `hermes-agent.image` to:

```yaml
image: joblandagent-hermes-agent:latest
```

Do not remove the `hermes-agent-data` volume.

- [ ] **Step 2: Update deploy script**

Update `scripts/deploy-hermes.sh` so it:

1. Builds `joblandagent-hermes-agent:latest` locally for `linux/amd64`.
2. Ships it to `hermes` with `docker save joblandagent-hermes-agent:latest | gzip | ssh hermes 'gunzip | docker load'`.
3. Stages compose.
4. Validates compose.
5. Runs `docker compose up -d`.
6. Prints `docker compose ps`.

Remove `docker compose pull` for the custom agent image. Keep `deploy-agent-mcp-config.sh` only if needed for runtime secret validation; otherwise do not rely on it for non-secret MCP config.

- [ ] **Step 3: Validate compose config locally if possible**

Run: `docker compose -f deploy/hermes-compose.yml config -q`

Expected: PASS, assuming required compose env defaults are present or provided.

### Task 6: Verification And Deployment Smoke Test

**Files:**
- Modify only if verification exposes a concrete issue.

- [ ] **Step 1: Run unit tests**

Run: `pytest tests/test_hermes_profile_bootstrap.py -v`

Expected: PASS.

- [ ] **Step 2: Build final image**

Run: `docker buildx build --platform linux/amd64 -t joblandagent-hermes-agent:latest --load -f docker/hermes-agent/Dockerfile .`

Expected: PASS.

- [ ] **Step 3: Run deploy script if image build passes**

Run: `scripts/deploy-hermes.sh`

Expected: Hermes stack recreates without removing volumes.

- [ ] **Step 4: Verify server state**

Run:

```bash
ssh hermes "cd /docker/hermes-workspace-dwys && docker compose ps"
ssh hermes "cd /docker/hermes-workspace-dwys && docker compose exec -T hermes-agent python - <<'PY'
from pathlib import Path
import yaml
p = Path('/opt/data/profiles/joblandagent')
cfg = yaml.safe_load((p / 'config.yaml').read_text()) or {}
assert (p / 'mcp.json').exists()
assert cfg.get('mcp_servers', {}).get('jobland', {}).get('url') == 'https://mcp.zall.dev/mcp'
assert (p / '.env').exists()
assert (p / 'state.db').exists()
print('ok')
PY"
```

Expected: both commands succeed.
