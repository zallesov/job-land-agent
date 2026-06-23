#!/usr/bin/env bash
# Build the dashboard image and ship it to the hermes server.
# Usage: scripts/deploy-dashboard.sh
set -euo pipefail

cd "$(dirname "$0")/../dashboard"

echo "==> building joblandagent-dashboard:latest (linux/amd64)"
docker buildx build --platform linux/amd64 -t joblandagent-dashboard:latest --load .

echo "==> shipping image to hermes"
docker save joblandagent-dashboard:latest | gzip | ssh hermes 'gunzip | docker load'

echo "==> recreating container"
ssh hermes 'cd /docker/joblandagent-dashboard && docker compose up -d'

echo "==> done"
ssh hermes 'docker compose -f /docker/joblandagent-dashboard/docker-compose.yml ps'
