# JobLeads in-page search workflow

Use this when the JobLeads pipeline needs to find real results instead of relying on a pre-baked feed URL.

## Core rule

Do not treat `search/jobs?...` query params or `view=for-you` as the search interface. Open the plain jobs page and operate the visible controls.

Start page:
- `https://www.jobleads.com/es/jobs`
- or the current locale's `/jobs` page if the browser has already switched locale

## Observed UI elements

Typical inputs on the page:
- keyword/title input: `data-testid="search-form-keyword-ui-input"`
- country dropdown trigger: `data-testid="ui-select-search-country-dropdown-trigger"`
- country dropdown search box: `data-testid="ui-select-search-country-dropdown-input"`
- location input: `data-testid="search-form-location-input"`
- work-model input: `data-testid="new-sidebar-filter-select-job-location-type-ui-input"`
- submit button: `button[type="submit"]` / aria-label like `Search jobs`

## Reliable interaction order

1. Open the jobs page and wait for DOM content.
2. Check the currently active country first.
   - If the desired country is already active, do nothing.
   - The active country entry may not be safely clickable again.
3. If country needs changing:
   - open the country dropdown
   - type into the dropdown search input
   - click the matching country entry from the rendered list
   - if Playwright locator click fails on the visible item, fall back to page-context `element.click()` on the matching country link
4. Fill keyword/title from `config/user.yaml` `search_terms`.
5. Fill city/location.
6. If the user prefers remote, open the work-model dropdown and choose `Remote`.
7. Submit.
8. Verify success:
   - URL changed to a real search-results path
   - page contains job links (`a[href*="/job/"]`)
   - page body is not just the generic feed or an empty-state recommendation page

## Failure modes seen in session

### 1. Empty-state from `view=for-you`
Symptom:
- page says there are no matches for current filters
- meanwhile the plain jobs page or locale-specific jobs page has results

Meaning:
- the feed URL is not the real search flow

Fix:
- drive the visible search form instead of URL params

### 2. Country already selected
Symptom:
- trying to click the same country again times out or behaves inconsistently

Fix:
- detect the active country first and skip the country-selection step if it already matches

### 3. Locator click on country item fails
Symptom:
- visible country item exists, but Playwright `.click()` reports not visible / detached / not enabled

Fix:
- use page-context JS click on the matching country link element

### 4. Search fields filled but no navigation
Symptom:
- text is present in controls but body still shows the generic recommendation feed

Fix:
- confirm the submit button is enabled
- click submit explicitly
- verify post-submit URL/body before concluding zero results

## Extraction note

The resulting list page can include repeated title text and mixed locale strings. When climbing from a job link to a card container, prefer a container that includes markers like:
- `Remote`, `Hybrid`, `On-site`
- `Full time`, `Part time`
- relative posting time like `days ago`, `today`, `vor ...`, `Hace ...`

This is more durable than looking for one language-specific marker such as `Jornada completa`.
