#!/bin/bash
# Launch persistent Chrome with CDP exposed for Hermes + scraper scripts
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
  --remote-debugging-port=9222 \
  --user-data-dir="$HOME/.interviews-browser-profile" \
  --no-first-run \
  --no-default-browser-check \
  --enable-automation \
  --disable-blink-features=AutomationControlled \
  2>/dev/null &
echo "Chrome started (CDP: http://localhost:9222, profile: ~/.interviews-browser-profile)"
