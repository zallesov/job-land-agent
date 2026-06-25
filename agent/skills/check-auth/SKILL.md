---
name: check-auth
description: Use when verifying or restoring visible-browser authentication for JobLand providers.
---

# Check Auth

## Hard Rule

Do not run provider auth scripts or inspect local browser storage. Use the visible browser and JobLandMCP-exposed auth/provider checks only.

## Workflow

1. If a JobLandMCP provider-auth check tool exists, call it for the requested provider.
2. If no MCP check exists, open the provider login or jobs page in the visible browser.
3. Let the user enter credentials manually.
4. Confirm by navigating to an authenticated provider page and checking visible page state.

## Provider Login URLs

- Greenhouse: `https://my.greenhouse.io/users/sign_in`
- JobLeads: `https://www.jobleads.com/login`
- Wellfound: `https://wellfound.com/login`
- Sprout: `https://app.usesprout.com/login`

Do not read cookies, local profiles, browser storage files, or backend records.
