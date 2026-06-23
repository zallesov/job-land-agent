#!/usr/bin/env bash
# Daily Job Pipeline Runner
# Called by Hermes cron. Uses PocketBase only; job data never goes through SQLite.
set -euo pipefail

cd "$(dirname "$0")/.."
DATE=$(date +%Y-%m-%d)
START=$(date +%s)

echo "=== Daily Pipeline $DATE ==="

RUN_ID=$(python3 -c "from scripts.pb_client import get_pb; print(get_pb().create_pipeline_run('daily_pipeline'))")
echo "Pipeline run: #$RUN_ID"

STATUS="succeeded"
FAILED=0

PROVIDERS=$(python3 - <<'PY'
import yaml
from pathlib import Path
cfg_path = Path('config/user.yaml')
cfg = yaml.safe_load(cfg_path.read_text()) if cfg_path.exists() else {}
providers = cfg.get('providers') or {}
for name, enabled in providers.items():
    if enabled:
        print(name)
PY
)

if [ -z "$PROVIDERS" ]; then
  echo "No enabled providers in config/user.yaml"
  STATUS="skipped"
fi

for provider in $PROVIDERS; do
  echo ""
  echo "--- Scraping $provider ---"
  if python3 scripts/scraping_pipeline.py --provider "$provider"; then
    echo "$provider: OK"
  else
    echo "$provider: FAILED" >&2
    FAILED=$((FAILED + 1))
    STATUS="partial"
  fi
done

if [ "$FAILED" -gt 0 ] && [ "$FAILED" -eq "$(printf '%s\n' $PROVIDERS | sed '/^$/d' | wc -l | tr -d ' ')" ]; then
  STATUS="failed"
fi

DURATION=$(( $(date +%s) - START ))

python3 - <<PY
import json
from scripts.pb_client import get_pb
get_pb().finish_pipeline_run(
    '$RUN_ID',
    '$STATUS',
    summary_json=json.dumps({'status': '$STATUS', 'duration_seconds': $DURATION, 'failed': $FAILED}),
)
PY

echo ""
echo "=== Done ($STATUS, ${DURATION}s) ==="
