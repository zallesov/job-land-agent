#!/bin/bash
# Launch persistent Chrome with CDP exposed for Hermes + scraper scripts
# Profile lives inside the project directory (portable / open-source friendly)

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROFILE_DIR="$SCRIPT_DIR/.chrome-profile"

/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
  --remote-debugging-port=9222 \
  --user-data-dir="$PROFILE_DIR" \
  --no-first-run \
  --no-default-browser-check \
  --enable-automation \
  --disable-blink-features=AutomationControlled \
  --restore-last-session \
  --use-mock-keychain \
  2>/dev/null &

echo "Chrome started (CDP: http://localhost:9222, profile: $PROFILE_DIR)"
