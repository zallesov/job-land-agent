# CDP Scraping Patterns

Shared patterns that apply to ALL CDP-based scrapers (Greenhouse, JobLeads, WellFound, Sprout).

## Core Pattern: connect_over_cdp

All scrapers connect to the user's existing Chrome via CDP — no separate Chromium launch:

```python
browser = pw.chromium.connect_over_cdp("http://localhost:9222")
context = browser.contexts[0]
page = context.new_page()
```

This inherits the Chrome profile (cookies, auth tokens, DataDome challenges, saved searches).

## Stale Page Cleanup (CRITICAL)

`connect_over_cdp` connects to the EXISTING browser context. If prior runs left pages open, they clutter `context.pages` and break new-page detection.

```python
for p in list(context.pages):
    try:
        p.close()
    except Exception:
        pass
page = context.new_page()
```

**Symptom if missed:** `wait_for_event("page")` times out. New tabs appear but aren't detected because they were opened in a prior run.

## React Handler: JS click() Required

Many modern SPAs (Sprout, and increasingly others) use React event handlers. Playwright's `locator.click()` fires a synthetic DOM event that React ignores.

**Fix:** Use `page.evaluate()` for native DOM click:

```python
page.evaluate("""() => {
    const buttons = document.querySelectorAll('button');
    for (const b of buttons) {
        if (b.innerText.includes('Target Text')) {
            b.click();  // native DOM click — triggers React
            return true;
        }
    }
    return false;
}""")
```

**Symptom if missed:** Button is found, `is_visible()` returns true, but clicking produces no effect (no navigation, no new page, no state change).

## React Portal Autocomplete

Autocomplete dropdowns often render in React portals (outside the normal DOM hierarchy). Playwright locators cannot see portal elements — they exist in the DOM but locators return 0 matches.

**Fix — three-step JS approach:**
1. JS `focus()` on the input
2. `keyboard.type(text, delay=50)` to trigger autocomplete
3. JS `evaluate()` to find and click `[role="option"]`

```python
page.evaluate("""() => {
    const input = document.querySelector('input[placeholder*="Location"]');
    if (input) input.focus();
}""")
page.keyboard.type("Berlin", delay=50)
page.wait_for_timeout(2000)
page.evaluate("""() => {
    const opts = document.querySelectorAll('[role="option"]');
    for (const o of opts) {
        if (o.innerText.includes('Berlin')) { o.click(); return; }
    }
}""")
```

**Symptom if missed:** Text is typed but location filter has no effect. Global results instead of location-filtered.

## Chip Overlay Blocking Click

After typing a search term, SPAs often render a chip/tag (e.g. `"AI Engineer"`) that visually overlaps adjacent inputs. Playwright's `click()` hits the chip instead: `<div>"AI Engineer"</div> subtree intercepts pointer events`.

**Fix:** Use JS `focus()` instead of Playwright `click()` to focus the blocked input. The chip only blocks pointer events — it doesn't prevent keyboard focus.

## New Tab URL Capture

When a button opens a URL in a new tab (common for "View Original" / "Apply" buttons):

```python
pages_before = {p.url for p in context.pages}
# Trigger the action (JS click, form submit, etc.)
page.wait_for_timeout(2000)
for p in context.pages:
    if p.url not in pages_before and "internal-domain.com" not in p.url:
        url = p.url
        p.close()  # clean up
        return url
```

**Alternative:** `context.expect_page()` before clicking — but this fails if the button uses JS navigation instead of `window.open()`.

## New Provider Registration Checklist

When adding a new provider to the pipeline, these files need updates:

1. `config/pipeline_config.json` — add source entry
2. `scripts/scrape_<provider>.py` — scraper script
3. `scripts/consolidate_provider_run.py` — add to `choices=[...]` in argument parser
4. Skill file under `skills/<provider>-scraper/`
5. `skills/job-scraping-pipeline/SKILL.md` — reference the new skill

Missing step 3 causes: `error: argument --provider: invalid choice`.
