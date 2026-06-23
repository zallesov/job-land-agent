# JobLeads search page behavior

## Symptom

Pipeline reports:
- `No job links found for Berlin Remote`
- `scraped 0 jobs`

…but a manually opened JobLeads page clearly shows many results.

## Root cause

The current scraper can land on a zero-results page because it hardcodes a URL-based `for-you` feed:

`https://www.jobleads.com/search/jobs?view=for-you&location_country=DE&filter_by_contractType=full_time&filter_by_remote=remote`

On JobLeads, `https://www.jobleads.com/search/jobs` is primarily a search UI / saved-search entrypoint. After login it may redirect to a localized results URL such as:

`https://www.jobleads.com/es/jobs?lastExecutedSearch=<id>`

That redirected page can contain real results even when the hardcoded `for-you` URL returns:

`Für deine aktuellen Filter wurden keine Job-Matches gefunden`

## Practical debugging recipe

1. Open `https://www.jobleads.com/search/jobs` in the headed Chrome session.
2. Check the final URL after redirect.
3. Inspect page text for either:
   - a real result count like `100+ Ergebnisse`
   - or the zero-results message `Für deine aktuellen Filter wurden keine Job-Matches gefunden`
4. Compare that with the exact URL the scraper constructs.

## Durable lesson

Do not assume JobLeads search is controlled by URL params alone. If the pipeline gets zero jobs, verify whether the site expects the search form / saved-search workflow to be driven in-page rather than by direct querystring navigation.

## Evidence captured in session

- Plain `/search/jobs` redirected to `/es/jobs?lastExecutedSearch=...` and showed `100+ Ergebnisse`.
- The scraper's hardcoded `view=for-you&location_country=DE&filter_by_contractType=full_time&filter_by_remote=remote` URL loaded, but showed no matches.
