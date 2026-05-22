---
name: sprout-scraper
description: Knows how to invoke the Sprout scraper script with CDP connection to local Chrome. Sprout aggregates jobs from ATS systems. Use when running the sprout scraping step of the daily pipeline.
---

# Sprout Scraper (CDP via Local Chrome)

**HARD RULE:** All Sprout scraping MUST use `pw.chromium.connect_over_cdp("http://localhost:9222")`. Sprout uses Supabase auth with Google OAuth — the Chrome profile must be pre-authenticated.

## Script

```
cd /Users/zall/interviews && python3 scripts/scrape_sprout.py
```

## Parameters

| Flag | Default | Description |
|------|---------|-------------|
| *(none required)* | — | Locations and titles read from `config/user.yaml` automatically |
| `--titles <str...>` | config `search_terms` | Override: job titles to search (one search per title) |
| `--cdp-url <url>` | `http://localhost:9222` | CDP endpoint |
| `--date <YYYY-MM-DD>` | today | Output filename date stamp |
| `--max-jobs <N>` | 0 (all) | Limit total jobs across all searches |

Locations are resolved from `config/user.yaml` → `locations[]` → `country_code` (DE → berlin, ES → spain).

## Output

```
outputs/sprout/runs/sprout_jobs_live_<date>_<location_slug>.json
```

## How It Works

Sprout displays jobs in a board view (`/jobs?view=board`). Each card shows company + title + metadata. Clicking a card opens a detail panel; "View Original" button navigates to the source ATS URL (Ashby, Greenhouse, Lever, etc.).

1. **Connect** — `connect_over_cdp` to local Chrome
2. **Navigate** — load `/jobs?view=board`
3. **Set work location filter** — reads `config/user.yaml` → `work_style.preferred` (remote/hybrid/onsite), opens the Filters dropdown, expands Work Location, sets the correct checkbox (Remote/Hybrid/In Person), unchecks the other two, unchecks "Include unknown work location" for exact-match-only results. Uses the same pattern as Greenhouse's `set_work_type_on_page()`.
4. **Search** — for each title: type in search bar, click Search, wait for results
5. **Collect** — enumerate cards, click each, click "View Original", capture URL, go back
6. **Dedup** — by original URL (cross-search dedup)
7. **Output** — JSON per location

### Work Location Filter Selectors

The Filters dropdown uses a Radix UI dropdown menu. Key selectors:

```
Filters button:  button[data-slot="dropdown-menu-trigger"]:has-text("Filters")
Work Location:   [role="menuitem"]:has-text("Work Location")
Checkboxes:      [role="menuitemcheckbox"]:has-text("Remote")
                 [role="menuitemcheckbox"]:has-text("Hybrid")
                 [role="menuitemcheckbox"]:has-text("In Person")
Unknown toggle:  [role="menuitemcheckbox"]:has-text("Include unknown work location")
```

Checkbox state is read via `aria-checked` attribute. Toggle only when current state differs from desired state. Always close dropdown with `Escape` when done.

## Dedup Strategy

Jobs are deduplicated by **original URL** (the ATS listing URL). Since different search terms can match the same job, the scraper:
- Tracks seen URLs across all searches
- Skips cards whose original URL was already captured
- Falls back to (company + title) dedup within a single search

## Pre-Flight Checklist

1. **Chrome must be running**: `curl -s http://localhost:9222/json/version`
2. **Chrome must be authenticated** with Sprout (Google OAuth complete)
3. First sign-in: navigate to `https://app.usesprout.com/jobs?view=board`, complete Google OAuth

## Pitfalls

### 1. Playwright click() does NOT fire React handlers (CRITICAL)

Sprout's "View Original" button uses React event handlers. Playwright's `locator.click()` fires a synthetic DOM event that React ignores. The button IS found and `is_visible()` returns true, but clicking it produces no navigation, no new page, nothing.

**Fix:** Use `page.evaluate()` to call the native DOM `click()` method, which triggers React's synthetic event system properly:

```python
page.evaluate("""() => {
    const buttons = document.querySelectorAll('button');
    for (const b of buttons) {
        if (b.innerText.includes('View Original')) {
            b.click();  // native DOM click — triggers React handler
            return true;
        }
    }
    return false;
}""")
# Then wait for new page to appear in context.pages
```

**Symptom if missed:** `context.wait_for_event("page")` times out after 6-15 seconds. No new pages appear in `context.pages`. The original URL falls back to the Sprout board URL.

### 2. Stale pages from prior runs block new page detection

`connect_over_cdp` connects to the EXISTING browser context. If prior script runs or browser interactions left ATS pages open (Workday, Greenhouse, etc.), they clutter `context.pages` and make new page detection unreliable.

**Fix:** Close ALL existing pages before starting:

```python
for p in list(context.pages):
    try:
        p.close()
    except Exception:
        pass
page = context.new_page()
```

### 3. Greenhouse URLs get ?error=true

When Sprout opens a Greenhouse-hosted job, the URL sometimes includes `?error=true`. This happens because Greenhouse checks the Referer header, and the new-tab navigation from Sprout may not send one. The job page still loads, but the error parameter is cosmetic. The URL is still valid for dedup and application.

### 4. Location autocomplete renders in React portal

Typing "Berlin" into the location input triggers an autocomplete dropdown. The options (`[role="option"]`) render in a **React portal** outside the normal DOM hierarchy. Playwright locators CANNOT see portal elements. The dropdown items exist in the DOM but are invisible to `page.locator()`.

**Fix — three-step JS approach:**
1. JS `focus()` on the location input (avoids chip overlay blocking Playwright click)
2. `keyboard.type(location, delay=50)` to enter text
3. JS `evaluate()` to find and click the matching `[role="option"]`

```python
page.evaluate("""() => {
    const input = document.querySelector('input[placeholder*="Anywhere"]');
    if (input) input.focus();
}""")
page.keyboard.type(location, delay=50)
page.wait_for_timeout(2000)
page.evaluate(f"""(loc) => {{
    const opts = document.querySelectorAll('[role="option"]');
    for (const o of opts) {{
        if (o.innerText.includes('{location}')) {{ o.click(); return; }}
    }}
}}""")
```

### 5. "AI Engineer" chip overlay blocks location input click

After typing a job title, Sprout renders a chip/tag (e.g., `"AI Engineer"`) that visually overlaps the location input. Playwright's `click()` hits the chip instead of the input. The error is: `<div>"AI Engineer"</div> subtree intercepts pointer events`.

**Fix:** Use JS `focus()` instead of Playwright `click()` to focus the input (see pitfall 4 above).

### 7. Experience/Seniority filter silently blocks non-Executive roles

Sprout's Filters dropdown has an \"Experience\" section (shows as `menuitem \"Experience N\"` where N is the number of active experience-level filters). If any level is checked (e.g., \"Executive\"), the board ONLY shows jobs at that level — blocking Staff, Principal, Senior, and individual-contributor roles that Zall wants.

**Symptom:** \"Staff Software Engineer\" search returns 2-4 cards instead of 10+, \"AI Engineer\" returns only C-suite/VP roles with \"Director\" or \"Head of\" in the title.

**Fix:** The scraper does NOT programmatically control this filter (it relies on browser session state). The user must open the Filters dropdown in their Chrome, expand \"Experience\", and ensure NO experience levels are checked (or at minimum that \"Executive\" is unchecked). Then re-scrape.

**Detection:** Compare the previous run's card counts. If \"AI Engineer\" dropped from ~14 to ~8 cards between runs with no other changes, check the Experience filter.

### 8. Dedup pre-check skips already-ingested cards

Before scraping, the script queries `jobs.db` for existing Sprout job URLs and prints `[dedup] N jobs already in DB — will skip matching cards`. Cards whose original URL matches an already-ingested job are still listed during collection but will not be re-enriched or re-added. This makes re-runs much faster (only new jobs get the expensive click-enrich cycle).

The dedup is URL-based — if the same job appears under a different ATS URL across runs, it will be treated as new. This is rare but possible when companies migrate ATS platforms.

## Success Check

Exit code 0. Stdout contains JSON with `count` > 0. Output file is valid JSON array.

## Reference Docs

- `references/cdp-scraping-patterns.md` (in `job-scraping-pipeline`) — Shared CDP patterns: React click, portal autocomplete, stale pages, new provider checklist
