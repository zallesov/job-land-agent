# Explee Company Discovery Pitfalls

## "Remote Teams" filter is unreliable

Explee's "Remote Teams" filter reflects company policy claims, not actual job-by-job remote eligibility. Companies tagged as remote-first regularly post roles that are hybrid or on-site:

- **H Company** (hcompany.ai): Tagged remote-first on Explee → ALL roles on Ashby listed as Hybrid (Paris, London, US)
- **FlexAI** (flex.ai): Tagged remote-first, globally distributed → ALL roles on Rippling ATS were on-site (Santa Clara, US)
- **Peak** (peak.ai): Tagged remote → Only US-based roles found via API

**Rule**: After identifying a company on Explee, always verify remote eligibility per-role via the actual ATS, not the Explee tag.

## Explee search filter strategy

Effective filter combinations for finding European AI companies:

1. **Broad sweep**: `AI + Remote Teams + Europe + Hiring NOW + SaaS + Tech Company + 50–2000 employees`
   → Yields 80-400 companies depending on filters

2. **Mid-large companies**: `AI + Europe + 200 employees`
   → 60-150 results, higher quality, fewer agencies

3. **Niche discovery**: Vary filters to catch companies that don't appear in broad sweeps
   - Drop "Remote Teams" to find hybrid-friendly companies that may have remote roles
   - Drop "Europe" and add country-specific: "Germany", "Netherlands", "UK"
   - Add "Series B+"/"Series C+" for funded growth-stage

## Domain extraction from Explee

After search results load, use browser_console to extract company domains:
```js
// Extract all company names and domains from the results page
Array.from(document.querySelectorAll('[data-testid="company-card"]')).map(c => ({
  name: c.querySelector('.company-name')?.textContent?.trim(),
  domain: c.querySelector('a[href*="http"]')?.href
}))
```

The exact selectors vary by Explee's current markup — inspect via browser_snapshot first.

## Speed Trap: do NOT use subagents for batch company checking

Subagents with 5+ companies each will timeout at 600s. Instead:
1. Extract all companies from Explee into a JSON file
2. Use a single Python script to batch-curl Greenhouse/Ashby/Lever APIs (2-4 seconds per company)
3. Only open browser for companies using custom ATS or Workday
