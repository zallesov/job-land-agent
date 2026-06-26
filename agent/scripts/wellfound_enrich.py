#!/usr/bin/env python3
"""
Enrich Wellfound shortlist jobs by visiting each detail page — up to 5 concurrent tabs in
the ONE authenticated local Chrome (CDP 9222), via Playwright connect_over_cdp.

Per job it pulls what the feed could not: company, external apply URL, full description,
real compensation/location. Input rows are JobLand records (from wellfound_fetch, status=new)
carrying their MCP `id`. The moment a job finishes enriching, its result is written back to
JobLand via JobLandMCP (status -> "enriched"), so progress is durable per job and the run is
resumable from DB status (re-fetch status=new and you only get what is left). DB writes are
JobLandMCP-only (scripts.mcp_client); `--no-db` disables them for a dry/smoke run.

Two browser modes:
  - default (connect): attach to the running visible/xvfb Chrome over CDP and reuse its
    authenticated context (contexts[0]). Parallel tabs share the real cookies.
  - --headless: launch our own headless Chrome (real Chrome binary, stealth flags) and
    load the carried session (--state session.json). For server/cron runs that should not
    depend on a visible browser. Note: wellfound.com is DataDome-protected — headless is
    more detectable, so pair it with a residential proxy (--proxy) and the matching
    --user-agent, or expect challenges.

Why Playwright (not agent-browser): parallel tabs must share one authenticated context;
asyncio drives several pages at once. agent-browser's isolated --session would lose login.

Usage:
  # attach to running CDP Chrome (default)
  python3 scripts/wellfound_enrich.py tmp/wellfound/shortlist.json \
      --out tmp/wellfound/enriched.json --concurrency 5 [--limit N]
  # own headless Chrome with carried session
  python3 scripts/wellfound_enrich.py tmp/wellfound/shortlist.json --headless \
      --state session.json --user-agent "<UA>" --proxy http://host:port
"""
import argparse, asyncio, json, re, sys
from pathlib import Path
from playwright.async_api import async_playwright

CDP = "http://127.0.0.1:9222"
JOB_ID = re.compile(r"/jobs/(\d+)")
# Profile root = parent of scripts/ — so default tmp/ paths resolve no matter the cwd
# (works whether invoked as scripts/... from the profile root or agent/scripts/... from the repo).
ROOT = Path(__file__).resolve().parents[1]
def under_root(rel):
    return str(ROOT / rel)

# Runs in the page. Combines SSR __NEXT_DATA__ (metadata) with rendered DOM (apply URL).
EXTRACT_JS = r"""
() => {
  const t = el => (el?.textContent || "").trim();
  const out = { title:null, company:null, compensation:null, locations:[], remote:null,
                jobType:null, source:null, apply_url:null, description:null };

  // --- SSR Apollo cache: find the JobListing + its Startup ---
  try {
    const d = JSON.parse(document.querySelector("#__NEXT_DATA__").textContent);
    const data = d?.props?.pageProps?.apolloState?.data || {};
    let job=null, startup=null;
    for (const k in data) {
      if (k.startsWith("JobListing:") && data[k].title && !job) job = data[k];
      if (k.startsWith("Startup:") && !startup) startup = data[k];
    }
    if (job) {
      out.title = job.title ?? out.title;
      out.compensation = job.compensation ?? job.salary ?? null;
      out.remote = job.remote ?? job.remoteOk ?? null;
      out.jobType = job.jobType ?? null;
      out.source = job.source ?? null;
      out.locations = (job.liveLocations || job.locationNames || job.locations || [])
        .map(x => typeof x === "string" ? x : (x?.displayName || x?.name)).filter(Boolean);
      const desc = job.description || job.descriptionPlain || "";
      out.description = desc.replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").trim() || null;
    }
    if (startup) out.company = startup.name || startup.companyName || out.company;
  } catch (e) {}

  // --- DOM fallbacks ---
  if (!out.company) {                       // page <title> = "<role> at <company> • ..."
    const m = document.title.match(/\bat\s+(.+?)\s*[•|]/);
    if (m) out.company = m[1].trim();
  }
  if (!out.title) out.title = t(document.querySelector("h1")) || null;
  if (!out.description) {
    const dn = document.querySelector('[class*="description"]') || document.body;
    out.description = t(dn).slice(0, 8000) || null;
  }
  // apply URL: the rendered "Apply" anchor (external ATS link). For in-app Wellfound
  // apply (no external anchor) fall back to the Wellfound job URL itself.
  const apply = [...document.querySelectorAll("a")].find(a => /apply/i.test(t(a)) && a.href);
  out.apply_url = apply ? apply.href : location.href.split("?")[0];
  out.apply_type = apply ? "external" : "in_app";
  return out;
}
"""


def job_key(j):
    """Stable per-job key for resume/dedup: wellfound id, else the url."""
    u = j.get("url") or ""
    m = JOB_ID.search(u)
    return m.group(1) if m else (u or None)


def to_jobland_fields(rec: dict) -> dict:
    """Map an enriched record to JobLand (PB) field names. Empty values omitted.

    Mirrors references/jobland-field-mapping.md (enrich-owned fields only). Note the
    PB schema field is `salary_range` (not `salary_raw`).
    """
    fields: dict = {}
    if rec.get("title"):
        fields["title"] = rec["title"]
    if rec.get("company"):
        fields["posted_company_name"] = rec["company"]
    if rec.get("apply_url"):
        fields["apply_url"] = rec["apply_url"]
    if rec.get("description"):
        fields["description"] = rec["description"]
    if rec.get("compensation"):
        fields["salary_range"] = rec["compensation"]
    locs = [l for l in (rec.get("locations") or []) if l]
    if locs:
        fields["location"] = ", ".join(locs)
    if rec.get("remote") is True:
        fields["remote_scope"] = "remote"
    return fields


def should_persist(rec: dict) -> bool:
    """Only write fully-enriched rows that carry a DB id and were not bot-blocked."""
    return bool(rec.get("enriched")) and not rec.get("blocked") and bool(rec.get("id"))


def persist(mcp, rec: dict) -> bool:
    """Write one enriched job back to JobLand via MCP, advancing status -> enriched.

    Returns True if written. Blocked / un-enriched / id-less rows are never written
    (so a bot-check halt leaves the blocked job at status=new for the next run).
    """
    if not should_persist(rec):
        return False
    mcp.update_job(rec["id"], status="enriched", **to_jobland_fields(rec))
    return True


# Detects a bot-check / CAPTCHA interstitial (DataDome slider, "verify you are human").
BOT_CHECK_JS = r"""
() => {
  if (document.querySelector('iframe[src*="captcha"], iframe[title*="DataDome"], iframe[src*="geo.captcha-delivery"]'))
    return true;
  const txt = (document.body && document.body.innerText || "");
  return /Access is temporarily restricted|verify you are (a )?human|confirm you('?re| are) not a (ro)?bot|slide to (complete|verify)|unusual activity from your (device|network)/i.test(txt);
}
"""


async def enrich_one(ctx, job, sem, idx, total, on_done, state):
    if state["blocked"].is_set():                # batch already halted by a bot-check
        return {**job, "blocked_skipped": True}
    async with sem:
        if state["blocked"].is_set():
            return {**job, "blocked_skipped": True}
        url = job["url"]
        page = await ctx.new_page()
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(1800)            # let client hydrate (apply btn)
            if await page.evaluate(BOT_CHECK_JS):        # CAPTCHA / slider hit
                state["blocked"].set()
                state["url"] = url
                print(f"  [{idx}/{total}] BOT-CHECK at {url} — halting batch", file=sys.stderr)
                return {**job, "blocked": True}
            data = await page.evaluate(EXTRACT_JS)
            data["ok"] = True
        except Exception as e:
            data = {"ok": False, "error": str(e)[:200]}
        finally:
            await page.close()
        if "ok" not in data:                         # blocked path returned above
            return {**job, "blocked": True}
        print(f"  [{idx}/{total}] {'OK ' if data.get('ok') else 'ERR'} "
              f"{data.get('company') or '?'} — {job.get('title','')[:40]}", file=sys.stderr)
        result = {**job, **{k: v for k, v in data.items() if k != "title" or not job.get("title")},
                  "enriched": data.get("ok", False)}
        if on_done:                       # checkpoint immediately so a crash can resume
            await on_done(result)
        return result


async def set_window_bounds(ctx, page, bounds):
    """Move/resize the browser window that holds `page` (best-effort, via CDP)."""
    try:
        cdp = await ctx.new_cdp_session(page)
        info = await cdp.send("Browser.getWindowForTarget")
        await cdp.send("Browser.setWindowBounds", {"windowId": info["windowId"], "bounds": bounds})
    except Exception:
        pass


ONSCREEN = {"left": 80, "top": 60, "width": 1200, "height": 900, "windowState": "normal"}


async def reveal_and_open(ctx, url):
    """Bring the (off-screen) window on-screen at `url` so the user can solve a bot-check."""
    page = await ctx.new_page()
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
    except Exception:
        pass
    await set_window_bounds(ctx, page, ONSCREEN)
    try:
        await page.bring_to_front()
    except Exception:
        pass


def find_chrome():
    """Locate a real Chrome/Chromium binary for headless launch."""
    import shutil
    for c in ("google-chrome-stable", "google-chrome", "chromium", "chromium-browser"):
        path = shutil.which(c)
        if path:
            return path
    mac = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    return mac if Path(mac).exists() else None


def load_checkpoint(path: Path):
    """Return {job_key: record} of jobs already enriched in a prior (possibly crashed) run."""
    done = {}
    if not path.exists():
        return done
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        k = job_key(r)
        if k:
            done[k] = r
    return done


async def run(args):
    data = json.loads(Path(args.shortlist).read_text())
    jobs = data.get("jobs", []) if isinstance(data, dict) else data
    if args.limit:
        jobs = jobs[:args.limit]

    # Resume: skip jobs already in the checkpoint so a crashed run never re-enriches them.
    checkpoint = Path(args.checkpoint or (Path(args.out).with_suffix(".jsonl")))
    done = {} if args.no_resume else load_checkpoint(checkpoint)
    pending = [j for j in jobs if job_key(j) not in done]
    print(f"resume: {len(done)} already enriched (checkpoint {checkpoint.name}), "
          f"{len(pending)}/{len(jobs)} to do", file=sys.stderr)

    checkpoint.parent.mkdir(parents=True, exist_ok=True)
    ckpt = checkpoint.open("a")
    lock = asyncio.Lock()

    write_db = not args.no_db
    if write_db:
        sys.path.insert(0, str(ROOT))
        from scripts.mcp_client import get_client  # noqa: PLC0415
        mcp = get_client()
    else:
        mcp = None
    counts = {"db": 0}

    async def on_done(rec):
        async with lock:                  # append-and-flush per job = crash-safe progress
            ckpt.write(json.dumps(rec, ensure_ascii=False) + "\n")
            ckpt.flush()
            if write_db:                  # durable per-job: status -> enriched in JobLand
                if await asyncio.to_thread(persist, mcp, rec):
                    counts["db"] += 1

    state = {"blocked": asyncio.Event(), "url": None}

    async with async_playwright() as p:
        owns_browser = False
        if args.headless:
            # Launch our own headless Chrome (real Chrome binary for stealth) with the
            # carried session, instead of attaching to a running CDP browser.
            launch_args = ["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu",
                           "--disable-blink-features=AutomationControlled"]
            proxy = {"server": args.proxy} if args.proxy else None
            browser = await p.chromium.launch(
                headless=True, executable_path=(args.executable_path or find_chrome()),
                args=launch_args, proxy=proxy)
            ctx_kwargs = {}
            if args.state and Path(args.state).exists():
                ctx_kwargs["storage_state"] = args.state      # cookies + localStorage
            if args.user_agent:
                ctx_kwargs["user_agent"] = args.user_agent
            ctx = await browser.new_context(**ctx_kwargs)
            owns_browser = True
        else:
            # Attach to the running (visible/xvfb) authenticated Chrome over CDP.
            browser = await p.chromium.connect_over_cdp(args.cdp)
            ctx = browser.contexts[0]

        sem = asyncio.Semaphore(args.concurrency)
        await asyncio.gather(
            *[enrich_one(ctx, j, sem, i + 1, len(pending), on_done, state)
              for i, j in enumerate(pending)])

        # Bot-check hit mid-batch: open the blocking URL on-screen for the user to solve.
        if state["blocked"].is_set() and not args.headless:
            await reveal_and_open(ctx, state["url"])

        if owns_browser:
            await ctx.close()
            await browser.close()

    ckpt.close()

    # Consolidate the full result (resumed + new) from the checkpoint; last write wins.
    all_recs = load_checkpoint(checkpoint)
    recs = list(all_recs.values())
    ok = sum(1 for r in recs if r.get("enriched"))
    Path(args.out).write_text(json.dumps(
        {"count": len(recs), "enriched_ok": ok, "jobs": recs}, indent=2, ensure_ascii=False))
    db_note = f", {counts['db']} written to JobLand (status=enriched)" if write_db else " (--no-db)"
    print(f"\nenriched total {ok}/{len(recs)} -> {args.out}  (checkpoint: {checkpoint}){db_note}")

    if state["blocked"].is_set():
        print(f"\n*** BOT-CHECK — enrichment halted at {state['url']}", file=sys.stderr)
        if args.headless:
            print("    Headless can't show a CAPTCHA. Re-run WITHOUT --headless against a "
                  "headed/Xvfb Chrome so the slider is visible.", file=sys.stderr)
        else:
            print("    A browser window was brought on-screen at that URL. Solve the slider "
                  "by hand, then re-run the same command — it resumes from the checkpoint "
                  "(done jobs are skipped).", file=sys.stderr)
        sys.exit(2)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("shortlist", nargs="?", default=under_root("tmp/wellfound/shortlist_new.json"))
    ap.add_argument("--out", default=under_root("tmp/wellfound/enriched.json"))
    ap.add_argument("--concurrency", type=int, default=5)
    ap.add_argument("--limit", type=int, default=None)
    # Resume: per-job JSONL checkpoint (default: <out>.jsonl). Crash-safe; skips done jobs.
    ap.add_argument("--checkpoint", default=None, help="JSONL checkpoint path (default <out>.jsonl)")
    ap.add_argument("--no-resume", action="store_true", help="Ignore existing checkpoint")
    ap.add_argument("--no-db", action="store_true",
                    help="Do not write results to JobLand (dry/smoke run; file output only)")
    # Connect mode (default): attach to the running CDP Chrome.
    ap.add_argument("--cdp", default=CDP, help="CDP endpoint to attach to (default mode)")
    # Headless mode: launch our own headless Chrome with the carried session.
    ap.add_argument("--headless", action="store_true",
                    help="Launch a headless Chrome instead of attaching to CDP")
    ap.add_argument("--state", default="session.json",
                    help="Session file (cookies+localStorage) for --headless")
    ap.add_argument("--user-agent", default=None, help="User-Agent for --headless context")
    ap.add_argument("--proxy", default=None, help="Proxy server for --headless (e.g. http://host:port)")
    ap.add_argument("--executable-path", default=None, help="Chrome binary for --headless")
    asyncio.run(run(ap.parse_args()))


if __name__ == "__main__":
    main()
