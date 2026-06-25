#!/usr/bin/env bash
# Deploy / update the Hermes agent stack on the hermes host.
#
# The Hermes agent image is built locally with the JobLandAgent profile baked
# in, then shipped to the host. The named volumes (hermes-agent-data,
# hermes-workspace-files) carry the agent's auth tokens + workspace and are
# preserved across recreation — this script never runs `down -v`.
#
# The host .env (COMPOSE_PROJECT_NAME, TRAEFIK_HOST, API keys, DASHBOARD_*,
# HERMES_PASSWORD, ...) already lives on the server and is NOT touched here.
#
# Usage: scripts/deploy-hermes.sh
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
REMOTE_DIR="/docker/hermes-workspace-dwys"

echo "==> building Hermes agent image (linux/amd64)"
docker buildx build --platform linux/amd64 \
  -t joblandagent-hermes-agent:latest \
  --load \
  -f "$REPO_ROOT/docker/hermes-agent/Dockerfile" \
  "$REPO_ROOT"

echo "==> shipping Hermes agent image to hermes"
docker save joblandagent-hermes-agent:latest | gzip | ssh hermes 'gunzip | docker load'

echo "==> staging compose on host (.env must already exist there)"
ssh hermes "mkdir -p $REMOTE_DIR"
scp "$REPO_ROOT/deploy/hermes-compose.yml" "hermes:$REMOTE_DIR/docker-compose.yml"

echo "==> validating compose on host"
ssh hermes "cd $REMOTE_DIR && docker compose config -q"

echo "==> pulling upstream workspace image"
ssh hermes "cd $REMOTE_DIR && docker compose pull hermes-workspace"

echo "==> recreating stack (volumes preserved — no down -v)"
ssh hermes "cd $REMOTE_DIR && docker compose up -d"

echo "==> status"
ssh hermes "cd $REMOTE_DIR && docker compose ps"

echo "==> validating JobLandAgent profile bootstrap"
ssh hermes "cd $REMOTE_DIR && timeout 60 sh -c 'until docker compose exec -T hermes-agent grep -q \"  jobland:\" /opt/data/profiles/joblandagent/config.yaml; do sleep 1; done'"
ssh hermes "cd $REMOTE_DIR && docker compose exec -T hermes-agent /opt/hermes/.venv/bin/python - <<'PY'
from pathlib import Path
import os
import yaml

profile = Path('/opt/data/profiles/joblandagent')
cfg = yaml.safe_load((profile / 'config.yaml').read_text()) or {}
server = cfg.get('mcp_servers', {}).get('jobland')
if not server:
    raise SystemExit('missing mcp_servers.jobland')
if server.get('url') != 'https://mcp.zall.dev/mcp':
    raise SystemExit('unexpected jobland MCP URL')
if not (profile / 'mcp.json').exists():
    raise SystemExit('missing profile mcp.json')
env_text = (profile / '.env').read_text() if (profile / '.env').exists() else ''
if not os.environ.get('MCP_JOBLAND_API_KEY') and 'MCP_JOBLAND_API_KEY=' not in env_text:
    raise SystemExit('missing MCP_JOBLAND_API_KEY in container env or profile .env')
print('ok')
PY"

echo "==> done — verify the Hermes dashboard host responds (e.g. https://<project>.<traefik-host>/login)"
