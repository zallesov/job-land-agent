#!/usr/bin/env bash
# Build + ship the combined JobLandAgent stack (pocketbase + dashboard + mcp)
# and recreate it on the hermes host at /docker/joblandagent/.
#
# PocketBase data is host-mounted (/opt/pocketbase/pb_data) and is NOT touched
# by this script beyond a normal container restart. A backup is taken first.
#
# Usage: scripts/deploy-stack.sh
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
REMOTE_DIR="/docker/joblandagent"

echo "==> backing up PocketBase data on host"
ssh hermes 'tar czf /opt/pocketbase/backup-$(date +%Y%m%d-%H%M%S).tgz -C /opt/pocketbase pb_data && ls -lh /opt/pocketbase/backup-*.tgz | tail -1'

echo "==> building images (linux/amd64)"
# The browser bundle hard-codes this PocketBase URL (NEXT_PUBLIC_*, build-time).
NEXT_PUBLIC_POCKETBASE_URL="${NEXT_PUBLIC_POCKETBASE_URL:-https://pb.zall.dev}"
docker buildx build --platform linux/amd64 \
  --build-arg "NEXT_PUBLIC_POCKETBASE_URL=$NEXT_PUBLIC_POCKETBASE_URL" \
  -t joblandagent-dashboard:latest --load "$REPO_ROOT/dashboard"
docker buildx build --platform linux/amd64 -t joblandagent-mcp:latest --load "$REPO_ROOT/mcp"

echo "==> shipping images to hermes"
docker save joblandagent-dashboard:latest joblandagent-mcp:latest | gzip | ssh hermes 'gunzip | docker load'

echo "==> staging compose on host (.env must already exist there)"
ssh hermes "mkdir -p $REMOTE_DIR"
scp "$REPO_ROOT/deploy/docker-compose.yml" "hermes:$REMOTE_DIR/docker-compose.yml"

echo "==> recreating combined stack"
ssh hermes "cd $REMOTE_DIR && docker compose up -d"

echo "==> status"
ssh hermes "cd $REMOTE_DIR && docker compose ps"
echo "==> done — verify: https://pb.zall.dev/api/health  https://jobs.zall.dev  https://mcp.zall.dev/healthz"
