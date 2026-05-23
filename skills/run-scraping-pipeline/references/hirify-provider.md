# Hirify Provider — Scraping Reference

## Provider setup

- Hirify does not use `search_terms`, `locations`, or `work_style` from `config/user.yaml`.
- The user must create **saved filters** manually at https://hirify.me/ before scraping will return results.
- Saved filters persist in the user's Hirify account; the scraper opens each one and collects all paginated jobs.
- Before first scrape, ensure `hirify: true` is in `config/user.yaml`'s `providers:` section.

## Scraper invocation

```bash
python3 scripts/scraping_pipeline.py --provider hirify
```

Uses the monolithic `scraping_pipeline.py` (not a standalone `scrape_hirify.py`).

## Authentication check

The scraper verifies before scraping via the Hirify auth check. If auth fails, it exits with code 10.

## Known quirks

### Saved filter index warnings (harmless)

The scraper iterates filter indices on the Hirify jobs page. Indices beyond the actual saved filters point to non-filter UI elements — notifications toggles, workflow preference dialogs, "Enable"/"Configure AI search" prompts, currency selection, etc.

Expected warnings (indices ~29–45):

```
[hirify] WARNING: saved filter 'Work type ? Exclude Full time Part time Project' failed: ... index not found: 29
[hirify] WARNING: saved filter 'Notifications for ...' failed: ... index not found: 44
[hirify] WARNING: saved filter 'Configure AI search How to search?' failed: ... index not found: 39
```

These are safe to ignore. They are not actual saved filters — they are UI controls that happen to have filter-like labels in the DOM.

### Raw title format

Hirify job listings come with a raw display string in the title field rather than a clean job title. Example:

```
"Company hidden\nhybrid\nNetherlands\nfulltime\nsenior\n3 seconds ago"
```

The enrichment step (when working) is responsible for extracting a clean title, description, and company name from the job URL.

### 'AI Jobs' saved filter overlay blocks clicks

The 'AI Jobs' saved filter (or any filter with a combobox) can trigger an HTML overlay (`<html class="light-mode ...">`) that intercepts all pointer events. The Playwright locator resolves the target button but the click hits the overlay and retries until timeout (30s).

This only affects saved filters that open a combobox/select on page load. Filters with static content work fine. If the 'AI Jobs' filter consistently fails, the scraper still collects jobs from the other working filters.

**No known fix from the scraper side** — the overlay is part of Hirify's React/Shoelace UI and the combobox `data-state="open"` attribute suggests it's already expanded. A workaround would be to close it first (Escape key or clicking elsewhere) before attempting to interact.
