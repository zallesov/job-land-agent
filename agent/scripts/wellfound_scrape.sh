#!/bin/bash
# Scrape the saved-search job feed at https://wellfound.com/jobs
#
# Uses the visible authenticated Chrome on CDP 9222 (see start-chrome.sh) driven by
# agent-browser. The account's saved search params are already applied server-side —
# this script just opens /jobs, exhausts the infinite scroll, and extracts every card.
#
# Feed cards are role-level: title, url, location, compensation, posted, badges.
# Company name is NOT in the feed (only on the job detail page) — enrich per-job if needed.
#
# Usage:  bash scripts/wellfound_scrape.sh [output.json]
#         OUT defaults to tmp/wellfound/jobs.json (relative to profile root).

set -euo pipefail
# Profile root = parent of scripts/ — default output resolves no matter the cwd.
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${1:-$ROOT/tmp/wellfound/jobs.json}"
mkdir -p "$(dirname "$OUT")"
CDP=9222
AB() { agent-browser --cdp "$CDP" "$@"; }

# 1. Chrome up?
if ! curl -s "http://localhost:$CDP/json/version" | grep -q '"Browser"'; then
  echo "Chrome not on :$CDP. Run: bash start-chrome.sh" >&2
  exit 1
fi

# 2. Reset the agent-browser daemon to THIS browser, open the feed.
agent-browser close --all >/dev/null 2>&1 || true
AB open https://wellfound.com/jobs >/dev/null
sleep 4

ROW='[class*="styles_jobListingList__"] [class*="styles_component__Ey28k"]'

# 3. Exhaust infinite scroll: scroll to bottom until the row count stops growing.
prev=-1; stable=0; iter=0
while [ "$iter" -lt 60 ]; do
  AB eval '(()=>{const s=document.scrollingElement;s.scrollTo(0,s.scrollHeight);return s.scrollHeight})()' >/dev/null 2>&1 || true
  sleep 2
  count=$(AB eval "document.querySelectorAll('$ROW').length" 2>/dev/null | tr -d '"' | tr -dc '0-9')
  count=${count:-0}
  echo "  scroll $iter: $count rows" >&2
  if [ "$count" -eq "$prev" ]; then
    stable=$((stable+1)); [ "$stable" -ge 3 ] && break   # 3 stable passes = end of feed
  else
    stable=0
  fi
  prev=$count; iter=$((iter+1))
done
echo "  feed exhausted at $prev rows" >&2

# 4. Extract every card. Prefix class selectors survive wellfound's hashed-class deploys.
RAW=$(AB eval '
(() => {
  const t = el => (el?.textContent || "").trim();
  const sel = (r,c) => t(r.querySelector(c));
  const rows = [...document.querySelectorAll(`[class*="styles_jobListingList__"] [class*="styles_component__Ey28k"]`)];
  const seen = new Set(); const out = [];
  for (const r of rows) {
    const a = [...r.querySelectorAll(`a[href*="/jobs/"]`)].find(x => /\/jobs\/\d+/.test(x.href));
    if (!a) continue;
    const url = a.href.split("?")[0];
    const m = url.match(/\/jobs\/(\d+)/); const id = m ? m[1] : null;
    if (seen.has(id)) continue; seen.add(id);
    const raw = t(r).replace(/\s+/g, " ");
    const comp = sel(r, `[class*="styles_compensation__"]`) || null;
    out.push({
      id, url,
      title:        sel(r, `[class*="styles_title__"]`) || (t(a) || null),
      location:     sel(r, `[class*="styles_location__"]`) || null,
      compensation: comp,
      salary:       (comp && comp.match(/[$€£][\d,]+k?\s*[–-]\s*[$€£]?[\d,]+k?/) || [null])[0],
      equity:       /no equity/i.test(comp || "") ? "none" : ((comp||"").match(/[\d.]+%\s*[–-]\s*[\d.]+%/)||[null])[0],
      posted:       (raw.match(/Posted [^•]+? ago/) || [null])[0],
      recruiterActive: /Recruiter recently active/i.test(raw),
      reposted:     /icn_repost/i.test(raw),
    });
  }
  return JSON.stringify({ scrapedAt: new Date().toISOString(), source: location.href, count: out.length, jobs: out });
})()
' 2>/dev/null)

# 5. agent-browser wraps the returned string in an extra JSON layer — unwrap, pretty-print.
TMP=$(mktemp)
printf '%s' "$RAW" > "$TMP"
python3 - "$OUT" "$TMP" <<'PY'
import json, sys
raw = open(sys.argv[2]).read().strip()
data = json.loads(raw)
if isinstance(data, str):           # unwrap agent-browser's outer string layer
    data = json.loads(data)
json.dump(data, open(sys.argv[1], "w"), indent=2, ensure_ascii=False)
print(f"\n{data['count']} jobs -> {sys.argv[1]}")
for j in data["jobs"][:8]:
    print(f"  [{j['id']}] {j['title']}  | {j.get('location')} | {j.get('compensation')}")
PY
rm -f "$TMP"
