#!/usr/bin/env bash
# Deploy JobLandAgent profile MCP configuration to the Hermes host.
#
# This updates only the JobLandAgent profile, not the default Hermes config:
#   /opt/data/profiles/joblandagent/config.yaml
#   /opt/data/profiles/joblandagent/.env
#
# Optional:
#   MCP_JOBLAND_API_KEY=<bearer-token> scripts/deploy-agent-mcp-config.sh
#
# If MCP_JOBLAND_API_KEY is omitted, the remote JobLandAgent profile .env must
# already contain it. This lets normal Hermes deploys refresh mcp.json without
# requiring the secret on the local machine every time.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
REMOTE_DIR="/docker/hermes-workspace-dwys"
REMOTE_JSON="$REMOTE_DIR/joblandagent-mcp.json"
REMOTE_MERGE="$REMOTE_DIR/merge-agent-mcp-config.py"
PROFILE_DIR="/opt/data/profiles/joblandagent"

echo "==> staging JobLandAgent MCP config"
scp "$REPO_ROOT/agent/mcp.json" "hermes:$REMOTE_JSON"
scp "$REPO_ROOT/scripts/merge-agent-mcp-config.py" "hermes:$REMOTE_MERGE"

echo "==> merging config into JobLandAgent profile"
ssh hermes "cd $REMOTE_DIR && docker compose cp joblandagent-mcp.json hermes-agent:/tmp/joblandagent-mcp.json"
ssh hermes "cd $REMOTE_DIR && docker compose cp merge-agent-mcp-config.py hermes-agent:/tmp/merge-agent-mcp-config.py"
ssh hermes "cd $REMOTE_DIR && docker compose exec -T -e MCP_JOBLAND_API_KEY='${MCP_JOBLAND_API_KEY:-}' -e JOBLAND_PROFILE_DIR='$PROFILE_DIR' hermes-agent python /tmp/merge-agent-mcp-config.py"

echo "==> validating merged config"
ssh hermes "cd $REMOTE_DIR && docker compose exec -T hermes-agent python - <<'PY'
from pathlib import Path
import yaml

cfg = yaml.safe_load(Path('$PROFILE_DIR/config.yaml').read_text()) or {}
server = cfg.get('mcp_servers', {}).get('jobland')
if not server:
    raise SystemExit('missing mcp_servers.jobland')
if server.get('url') != 'https://mcp.zall.dev/mcp':
    raise SystemExit('unexpected jobland MCP URL')
if 'MCP_JOBLAND_API_KEY' not in Path('$PROFILE_DIR/.env').read_text():
    raise SystemExit('missing MCP_JOBLAND_API_KEY in profile .env')
print('ok')
PY"

echo "==> cleaning staged file"
ssh hermes "rm -f '$REMOTE_JSON' '$REMOTE_MERGE'"
