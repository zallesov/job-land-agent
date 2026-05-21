# Explee Company Discovery Pattern

## What Explee.com provides

A searchable database of companies with rich filters:
- Business type (SaaS, AI, startup, tech company, B2B, digital, merchant)
- Industry (NACE codes)
- Location (country, city, region — headquarters or customer location)
- Employee count (slider: 1–10,000+)
- Staff growth rate year-over-year
- Website traffic levels
- Funding data
- Technologies used
- Remote teams, founders origin, year founded

## Recommended search configurations for Zall

### Primary: Mid-large Berlin tech companies
- Describe: "tech company" (triggers auto-suggest for "Tech company")
- Country: Germany, City: Berlin
- Employee count: 200–10,000+ (slider 6–11 on the 1–12 scale)
- Growth: High + Growing + Stable (all checked)

### Alternative: AI-focused search
- Describe: "AI SaaS"
- Country: Germany, City: Berlin
- Employee count: 50–10,000+
- Check "AI" and "SaaS" checkboxes

### Search term variations
- "German tech company with 200 employees Berlin"
- "AI startup Berlin Germany"
- "software company Berlin"
- "deep tech AI Berlin"

## Results handling

### Extract domains
After search loads, run in browser_console:
```js
[...new Set(Array.from(document.querySelectorAll('a'))
  .map(a => {try{return new URL(a.href).hostname}catch{return null}})
  .filter(h => h && !h.includes('explee.com') && !h.includes('linkedin') && !h.includes('google'))
  .slice(0, 60))]
```

### Known DOM extraction issues
- The table uses complex grid structure — `role="gridcell"` and `role="row"` queries often return empty
- `document.querySelectorAll('a[href]')` may also return empty if links are in shadow DOM or iframes
- **Fallback**: Use `browser_snapshot(full=true)` and parse company names/domains from the text output
- Scrolling causes the page to go blank (empty snapshot) — avoid scrolling, use pagination instead

### Identifying product companies vs consultancies
Many results will be IT consultancies (Andersen, Brightgrove, netgo, Quantox). Filter for:
- Companies with their own product (check domain → look for careers/jobs page)
- Skip: "IT services", "outsourcing", "consulting", "software development services"
- Good signals: "B2B", "SaaS", "AI" tags + direct careers page

## Post-discovery workflow

After building a company list via Explee:

1. **Spawn parallel subagents** (2–3 at a time) to check each company's careers page
2. **Per subagent**: Navigate to company.com/careers or company.com/jobs, find the ATS URL (Greenhouse, Lever, Workday, Ashby, Personio), extract SWE/AI/ML roles
3. **Send Telegram notification per promising match** — individual message per job with: company, title, URL, location, why-it's-a-match
4. **Handle known blockers**:
   - SmartRecruiters (Bosch) → DataDome CAPTCHA, may not work
   - Workday (Siemens, large corps) → visual CAPTCHA on first load
   - Companies with no careers page → skip, mark as "no openings"

## Telegram notification format

Per-match template (use `send_message(target='telegram:Zall')`):
```
🎯 TOP MATCH — Company Name

Role Title

📍 Location

Why it's a match (1-2 lines about skill/experience alignment)

https://careers.company.com/job-id
```

Send individual messages per top match (not a single batch digest). Zall wants to act on each immediately.

## Pitfalls

- **Subagent timeout**: Complex ATS portals (Workday, SmartRecruiters) may take >600s and timeout. For these, set a shorter deadline and report what was found.
- **Explee blank page**: After scrolling or multiple interactions, Explee snapshot returns empty. Re-navigate fresh.
- **Lots of consultancies**: ~60% of results on broad searches are IT service/consulting firms. Be prepared to filter.
- **Cookie consent walls**: Most EU company sites have cookie dialogs. Click "Decline all" or use browser_console to dismiss.
