#!/usr/bin/env bash
# Deploy / update the Hermes agent stack on the hermes host.
#
# Hermes ships as prebuilt registry images, so a deploy is just: stage the
# compose file, pull the latest images, and recreate the containers. The named
# volumes (hermes-agent-data, hermes-workspace-files) carry the agent's auth
# tokens + workspace and are preserved across recreation — this script never
# runs `down -v`.
#
# The host .env (COMPOSE_PROJECT_NAME, TRAEFIK_HOST, API keys, DASHBOARD_*,
# HERMES_PASSWORD, ...) already lives on the server and is NOT touched here.
#
# Usage: scripts/deploy-hermes.sh
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
REMOTE_DIR="/docker/hermes-workspace-dwys"

echo "==> staging compose on host (.env must already exist there)"
ssh hermes "mkdir -p $REMOTE_DIR"
scp "$REPO_ROOT/deploy/hermes-compose.yml" "hermes:$REMOTE_DIR/docker-compose.yml"

echo "==> validating compose on host"
ssh hermes "cd $REMOTE_DIR && docker compose config -q"

echo "==> pulling latest images"
ssh hermes "cd $REMOTE_DIR && docker compose pull"

echo "==> recreating stack (volumes preserved — no down -v)"
ssh hermes "cd $REMOTE_DIR && docker compose up -d"

echo "==> status"
ssh hermes "cd $REMOTE_DIR && docker compose ps"
echo "==> done — verify the Hermes dashboard host responds (e.g. https://<project>.<traefik-host>/login)"
