# Hirify Saved Filters Provider Design

## Goal

Add Hirify as a first-class JobLandAgent provider that scrapes every job from every saved filter on `https://hirify.me/`. The user configures search criteria inside Hirify; JobLandAgent only opens those saved filters, collects all visible jobs, normalizes them, and feeds them into the existing pipeline.

## Scope

In scope:

- Add provider package `scripts/providers/hirify/`.
- Add authentication/session check for Hirify.
- Scrape all saved filters on Hirify.
- For each saved filter, collect every paginated result page.
- Normalize results to `scripts.pipeline.types.ShallowJob`.
- Deduplicate jobs across filters and pages.
- Wire Hirify into CLI/provider registries, onboarding, config examples, docs, and dashboard display colors.
- Add focused tests for provider registration, saved-filter scraping behavior, pagination, normalization, and integration text/config updates.

Out of scope:

- Building Hirify search URLs from JobLandAgent `search_terms`, `locations`, or `work_style`.
- Managing Hirify saved filters from JobLandAgent.
- Enriching Hirify detail pages beyond the shallow job fields needed by the existing pipeline.
- Scraping jobs that are not reachable through the user's saved filters.

## User Flow

1. The user logs into Hirify in the shared Chrome session.
2. The user configures and saves one or more filters on Hirify.
3. The user enables `providers.hirify: true` in `config/user.yaml` or selects Hirify during onboarding.
4. Running the scraping pipeline with provider `hirify` opens Hirify, enumerates saved filters, scrapes all jobs from each saved filter, deduplicates the results, and inserts new jobs through the existing pipeline.

## Architecture

Hirify follows the existing provider contract:

- `scripts/providers/hirify/check_auth.py` exposes `check_auth(cdp_url: str) -> None`.
- `scripts/providers/hirify/scrape_jobs.py` exposes `scrape_jobs(cdp_url: str, titles: list[str] | None = None, db_path: str | None = None, _config: dict | None = None) -> list[ShallowJob]`.

The scraper will connect to the existing Chrome instance through Playwright CDP, matching the other UI-based providers. It will not create an anonymous browser context because saved filters and authenticated state live in the user's browser profile.

## Hirify Scraping Behavior

The scraper opens `https://hirify.me/` and locates the saved filters UI. It then iterates through each saved filter in the list.

For each saved filter:

1. Activate the filter.
2. Wait until the job list updates.
3. Collect job cards from the current page.
4. Click `Next` while it is available and enabled.
5. Stop when `Next` is absent, disabled, or a page produces no new job URLs.

The primary traversal mode is pagination because Hirify exposes explicit `Previous 1 2 3 ... Next` controls. Infinite scroll may be used as a fallback if pagination controls are missing or the site changes, but the implementation should avoid relying on scroll as the only path.

The scraper should keep two seen sets:

- `seen_urls`: global across the whole provider run, so the same job matching multiple saved filters is returned once.
- `seen_page_signatures`: per saved filter, so pagination cannot loop forever if the UI repeats a page.

## Normalized Fields

Each Hirify job becomes a `ShallowJob`:

- `provider`: `hirify`
- `title`: parsed title text from the job card.
- `company`: parsed company name, or `Company hidden` when Hirify hides it.
- `url`: canonical Hirify job URL from the card link.
- `location`: compact text from the card when available, such as country/region/work format.
- `country`: parsed country when confidently available, otherwise `None`.
- `dedup_key`: `"{company}::{title}"` when both fields are available.
- `posting_date`: `None` for the shallow scrape unless a stable date is easy to parse.
- `salary_raw`: parsed salary text when present.
- `status`: `listed` when the existing relevance filter accepts the title, otherwise `skip`.

The `titles` argument must not change Hirify search criteria and must not filter the final Hirify result set. Saved filters are the source of truth for Hirify. This differs from providers that build searches from `search_terms`, and tests must lock this behavior down.

## Auth Handling

`check_auth` opens Hirify and treats the session as authenticated when saved filters or authenticated user controls are visible. It treats the session as unauthenticated when the page still shows `Sign In` and saved filters are unavailable.

When unauthenticated, it should use the shared auth wait helper pattern used by other providers and raise `AuthError("Hirify auth timed out")` after timeout.

## Integration Points

Update the following:

- `scripts/scraping_pipeline.py`: include `hirify` in `PROVIDERS` and help text.
- `scripts/providers/hirify/__init__.py`: provider package marker.
- `config/user.yaml.example`: include `providers.hirify`.
- `skills/onboarding/SKILL.md`: include Hirify in welcome text, provider choices, and generated config.
- `skills/run-scraping-pipeline/SKILL.md`: include Hirify in trigger examples and provider notes.
- `README.md`: add Hirify to supported job boards and usage examples.
- `dashboard/app/components/JobList.tsx`: add Hirify provider color.
- `dashboard/app/components/JobDetail.tsx`: add Hirify provider color if that component has its own map.
- `scripts/consolidate_provider_run.py` and `config/scraping-workflow.yaml`: include Hirify if they enumerate known provider IDs.

## Testing

Add focused tests without depending on the live Hirify site:

- Provider registry accepts `hirify`.
- `scrape_jobs` ignores config-driven search construction and opens Hirify directly.
- Saved filters are iterated.
- Pagination stops on disabled/missing `Next` or no new URLs.
- Duplicate jobs across filters are returned once.
- Raw Hirify card data normalizes to expected `ShallowJob` fields.
- Onboarding/config/docs references include Hirify where provider lists are hard-coded.

Live e2e validation can be manual because it requires the user's authenticated browser session and real saved filters.

## Error Handling

- If no saved filters are found while authenticated, return an empty list and print a clear warning telling the user to create saved filters on Hirify.
- If one saved filter fails to load, log a warning and continue with the next filter.
- If the whole site cannot be loaded, raise the Playwright exception so the existing pipeline failure notification handles it.
- If selectors drift, tests should fail around parser helpers rather than only in a live run.

## Open Decisions

None. The agreed behavior is to scrape every saved filter on Hirify, not to generate search parameters from JobLandAgent config.
