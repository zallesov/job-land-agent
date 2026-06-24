#!/usr/bin/env bash
# Apply db/pb_migrations/*.js to the remote PocketBase instance.
#
# PocketBase has no remote "migrate" API — migrations only run inside the
# pocketbase process itself, against the local pb_data. So "applying" means:
# ship the .js files to the host path the container mounts, then restart the
# container so its startup migration runner picks them up.
#
# This briefly bounces pocketbase and the dashboard/mcp that depend on it for
# the few seconds of the restart. The script stops and asks before that part.
#
# Usage: scripts/migrate-db.sh
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
MIGRATIONS_DIR="$REPO_ROOT/db/pb_migrations"
REMOTE_MIGRATIONS_PATH="/opt/pocketbase/pb_migrations"
REMOTE_COMPOSE="/docker/joblandagent/docker-compose.yml"
REMOTE_STACK_DIR="/docker/joblandagent"
VOLUME_LINE="      - ${REMOTE_MIGRATIONS_PATH}:/usr/local/bin/pb_migrations"

if [ -z "$(ls -A "$MIGRATIONS_DIR"/*.js 2>/dev/null)" ]; then
  echo "no migration files in $MIGRATIONS_DIR, nothing to do"
  exit 0
fi

echo "==> shipping migration files to hermes:$REMOTE_MIGRATIONS_PATH (safe, no restart yet)"
ssh hermes "mkdir -p $REMOTE_MIGRATIONS_PATH"
scp "$MIGRATIONS_DIR"/*.js "hermes:$REMOTE_MIGRATIONS_PATH/"

MOUNTED=0
if ssh hermes "grep -qF '$VOLUME_LINE' '$REMOTE_COMPOSE'"; then
  MOUNTED=1
fi

echo
echo "Files are on the server. Nothing live has changed yet."
if [ "$MOUNTED" -eq 0 ]; then
  echo "Next step needs your OK: add the volume mount to docker-compose.yml and"
  echo "restart the pocketbase container. This briefly bounces hermes-agent and"
  echo "the dashboard (a few seconds)."
else
  echo "Volume is already mounted. Next step needs your OK: restart pocketbase"
  echo "to pick up the new/changed migration files. Brief bounce for hermes-agent"
  echo "and the dashboard."
fi
read -r -p "Proceed with mount + restart now? [y/N] " ans
if [ "$ans" != "y" ] && [ "$ans" != "Y" ]; then
  echo "Stopped before the restart. Files are staged on the server; re-run this"
  echo "script when you're ready to apply them."
  exit 0
fi

if [ "$MOUNTED" -eq 0 ]; then
  echo "==> adding migrations volume to compose"
  ssh hermes "sed -i \"/pb_data:\\/usr\\/local\\/bin\\/pb_data/a\\\\
$VOLUME_LINE
\" '$REMOTE_COMPOSE'"
  ssh hermes "cd $REMOTE_STACK_DIR && docker compose config -q" \
    || { echo "compose file invalid after edit, aborting before restart"; exit 1; }
fi

echo "==> restarting pocketbase"
ssh hermes "cd $REMOTE_STACK_DIR && docker compose up -d pocketbase"

echo "==> waiting for healthy"
ssh hermes "timeout 30 sh -c 'until docker inspect -f \"{{.State.Health.Status}}\" pocketbase | grep -q healthy; do sleep 1; done'" \
  && echo "    healthy" || echo "    WARNING: did not report healthy within 30s, check logs"

echo "==> migration log lines from this boot"
ssh hermes "docker logs pocketbase --since 1m 2>&1 | grep -i migrat || echo '(no migration-related log lines found)'"

echo "==> done — verify https://jobs.zall.dev/api/jobs still works"
