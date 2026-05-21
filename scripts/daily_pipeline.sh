#!/usr/bin/env bash
# Daily Job Pipeline Runner
# Called by Hermes cron. Runs scrapers, ingest, tag, notify.
set -euo pipefail

cd "$(dirname "$0")/.."
DATE=$(date +%Y-%m-%d)
START=$(date +%s)

echo "=== Daily Pipeline $DATE ==="

# ── Step 0: Create pipeline run record ──
RUN_ID=$(python3 -c "
import sys; sys.path.insert(0, 'scripts')
from db import get_connection, create_pipeline_run
con = get_connection('jobs.db')
rid = create_pipeline_run(con, 'daily_pipeline')
con.commit()
print(rid)
con.close()
")
echo "Pipeline run: #$RUN_ID"

# ── Step 1: Scrape providers ──
GREENHOUSE_OK=false
JOBLEADS_OK=false

echo ""
echo "--- [1/4] Scraping Greenhouse (API) ---"
if python3 tmp/scrape_greenhouse_api.py; then
  GREENHOUSE_OK=true
  echo "Greenhouse: OK"
else
  echo "Greenhouse: FAILED (continuing)" >&2
fi

echo ""
echo "--- [2/4] Scraping JobLeads (headless) ---"
python3 scripts/scrape_jobleads.py --location spain --headless --date "$DATE" && \
  python3 scripts/scrape_jobleads.py --location berlin --headless --date "$DATE" && \
  JOBLEADS_OK=true || echo "JobLeads: FAILED (continuing)" >&2

# ── Step 3: Ingest ──
echo ""
echo "--- [3/4] Ingesting artifacts ---"
python3 scripts/ingest_provider_outputs.py --db jobs.db --all-latest

# ── Step 4: Tag ──
echo ""
echo "--- [4/4] Tagging new jobs ---"
python3 scripts/tag_new_jobs.py --db jobs.db

# ── Determine status ──
STATUS="failed"
if [ "$GREENHOUSE_OK" = true ] && [ "$JOBLEADS_OK" = true ]; then
  STATUS="succeeded"
elif [ "$GREENHOUSE_OK" = true ] || [ "$JOBLEADS_OK" = true ]; then
  STATUS="partial"
fi

DURATION=$(( $(date +%s) - START ))

# ── Finalize pipeline run ──
python3 -c "
import sys, json; sys.path.insert(0, 'scripts')
from db import get_connection, finish_pipeline_run
con = get_connection('jobs.db')
finish_pipeline_run(con, $RUN_ID, '$STATUS',
  summary_json=json.dumps({'status': '$STATUS', 'duration_seconds': $DURATION, 'greenhouse_ok': $GREENHOUSE_OK, 'jobleads_ok': $JOBLEADS_OK}))
con.commit()
con.close()
"

echo ""
echo "=== Done ($STATUS, ${DURATION}s) ==="
