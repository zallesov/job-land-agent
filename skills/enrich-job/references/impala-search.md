# Impala Search enrichment pitfalls

## Symptom: enrichment succeeds but title becomes `Apply Now`

Impala Search vacancy pages have two `<h1>` elements:
- sidebar apply form: `Apply Now`
- main vacancy content: `#vacancy-info h1`

A generic `document.querySelector('h1')` extractor will capture the sidebar CTA and write a bad title.

## Verification after enrichment

After enriching an Impala Search job, verify at least:
- title is not `Apply Now`
- location/salary match the vacancy specifics block
- description contains the actual responsibilities/qualifications text

## Reliable fallback extraction

The page is SSR and curl-readable. If Playwright/CDP fails, or if the extracted title is a generic CTA, fetch the HTML and extract from the main vacancy section instead of the sidebar form.

Relevant selectors/content patterns:
- title: `#vacancy-info h1`
- specifics block: `#vacancy-specifics`
- description block: `.jobdesc`

## Chrome profile isolation check

When restarting Chrome for enrichment, verify the launched process uses the active profile-local user-data-dir, not a developer checkout path.

Correct pattern for this profile:
- `--user-data-dir=/Users/zall/.hermes/profiles/joblandagent-dev/.chrome-profile`

If Chrome is started from another checkout/root and shows a different `.chrome-profile` path, stop and restart from the active profile root before trusting browser-driven pipeline runs.
