#!/bin/bash
# Launch persistent Chrome with CDP (port 9222) for Hermes + scraper scripts.
# Profile lives next to this script (.chrome-profile) — portable across machines/OS
# thanks to --use-mock-keychain (cookies are not tied to the OS keychain).
#
# Cross-platform:
#   macOS  -> the real Google Chrome.app, visible window.
#   Linux  -> google-chrome / chromium on a virtual display (xvfb) so a real "headed"
#             browser runs on a headless server (best DataDome stealth; avoids the
#             HeadlessChrome fingerprint). Container-safe flags (--no-sandbox).
#
# Optional env (mainly for the remote/container path B):
#   CHROME_PROXY  -> --proxy-server (use a residential-ish proxy on servers)
#   CHROME_UA     -> --user-agent   (match the UA the session was created with)
#   CDP_PORT      -> debugging port (default 9222)

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROFILE_DIR="${CHROME_PROFILE_DIR:-$SCRIPT_DIR/.chrome-profile}"
PORT="${CDP_PORT:-9222}"

# Common stealth/CDP flags (both platforms).
COMMON=(
  --remote-debugging-port="$PORT"
  --user-data-dir="$PROFILE_DIR"
  --no-first-run
  --no-default-browser-check
  --disable-blink-features=AutomationControlled
  --use-mock-keychain
)
[ -n "$CHROME_PROXY" ] && COMMON+=(--proxy-server="$CHROME_PROXY")
[ -n "$CHROME_UA" ]    && COMMON+=(--user-agent="$CHROME_UA")

case "$(uname -s)" in
  Darwin)
    # HIDDEN=1 -> real headed Chrome parked off-screen. DataDome sees a genuine headed
    # browser (passes), but no window is visible — the practical "local headless" since
    # true --headless is DataDome-blocked on protected sites (wellfound).
    MAC_EXTRA=(--restore-last-session)
    [ -n "$HIDDEN" ] && MAC_EXTRA=(--window-position=-32000,-32000 --window-size=1280,1800)
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
      "${COMMON[@]}" "${MAC_EXTRA[@]}" 2>/dev/null &
    ;;
  Linux)
    # Pick an available Chrome/Chromium binary.
    BIN=""
    for c in google-chrome google-chrome-stable chromium chromium-browser; do
      command -v "$c" >/dev/null 2>&1 && { BIN="$c"; break; }
    done
    if [ -z "$BIN" ]; then
      echo "No Chrome/Chromium found. Install google-chrome-stable (see docker/hermes-agent/Dockerfile)." >&2
      exit 1
    fi
    # Container-safe flags. Headed under a virtual display, NOT --headless, for stealth.
    LINUX_FLAGS=(--no-sandbox --disable-dev-shm-usage --disable-gpu --window-size=1280,1800)
    if [ -n "$DISPLAY" ]; then
      "$BIN" "${COMMON[@]}" "${LINUX_FLAGS[@]}" >/dev/null 2>&1 &
    elif command -v xvfb-run >/dev/null 2>&1; then
      xvfb-run -a --server-args="-screen 0 1280x1800x24" \
        "$BIN" "${COMMON[@]}" "${LINUX_FLAGS[@]}" >/dev/null 2>&1 &
    else
      echo "No DISPLAY and no xvfb-run. Install xvfb or set DISPLAY." >&2
      exit 1
    fi
    ;;
  *)
    echo "Unsupported OS: $(uname -s)" >&2
    exit 1
    ;;
esac

echo "Chrome started (CDP: http://localhost:$PORT, profile: $PROFILE_DIR)"
