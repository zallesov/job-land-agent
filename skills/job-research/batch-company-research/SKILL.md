---
name: batch-company-research
description: Research multiple companies from a list (Telegram post, message, forum) — find their websites, navigate to career pages, identify suitable SWE roles. Covers domain verification, career page discovery, role matching, and pipeline integration.
---

# Batch Company Research + Job Prospecting

When the user provides a list of company names (from a Telegram post like @zarubezhom_jobs, a message, or forum), do NOT just report the names. Proactively:

1. Identify the correct domain for each company
2. Navigate to their career/jobs page
3. Scan open roles matching the user's profile
4. Report findings + optionally add promising roles to the DB pipeline

## Step 1: Domain Discovery

**Common pitfalls with company names from Telegram/forum posts:**
- **Domain squatters**: `insense.com` is for sale — the actual company is `insense.pro`
- **Wrong TLD**: `prequel.com` is a domain squatter — the app is at `prequel.app`
- **SSL issues**: `kodland.com` has SSL errors — the real site is `kodland.org`
- **Rebrands**: "Fjor Health" renamed to "Formula" — neither domain resolves
- **Cyrillic/Latin mixups**: `Сonsuno` (Cyrillic С) → `Cosuno`
- **Generic names**: `theopenplatform.com` is parked (GoDaddy) — no working site found
- **Dead domains**: `ewa.com`, `getewa.com`, `ewa-app.com` all dead or for sale

**Methodology:** For each company name, try the most obvious domain first. If it fails (DNS error, SSL error, parked page, obvious wrong company), either:
- Google search the company name to find the real domain
- Check the company's LinkedIn page for their website link
- Report as "domain not found" if no alternative is found after reasonable effort

## Step 2: Career Page Discovery

Once on the company website, find the career/jobs page:
- Common paths to try: `/careers`, `/jobs`, `/company`, `/about`, `/en/careers`, `/web/en/company#careers`
- Check the footer and navigation for "Careers" / "Jobs" / "Join us" links
- Some sites use embedded ATS iframes (Ashby, Greenhouse, Lever) — these appear as iframes in the snapshot
- If the page is JS-heavy and the snapshot is truncated, use `browser_console` to extract `document.body.textContent`

## Step 3: Role Scanning

For each company with a career page, scan open engineering roles. Filter for:

**Target profile signals:**
- Senior/Staff/Principal level (not junior, intern, entry-level)
- Tech stack: Python, TypeScript, AI/ML, fullstack, backend, infrastructure
- Remote: EU remote, Berlin, or Spain
- Salary: €100k+ (or likely senior-market comp if not listed)
- AI-native companies (actually build with AI, not just list it)

**Role type priority:**
1. AI/ML Engineer, AI Engineer, ML Engineer — highest priority
2. Principal/Senior Full Stack (TypeScript/Python) — strong match
3. Staff/Principal Backend Engineer — good match
4. Platform/Security/Infrastructure Engineer — possible
5. SRE, Database Engineer — lower priority

## Step 4: Reporting

Present findings as a table:
- Company name | Role title | Salary | Remote | Verdict

Call out:
- The best matches (top 2-3)
- Companies with career pages but no visible SWE roles
- Companies where domain wasn't found

## Step 5: Pipeline Integration

If the user asks to add a role to the database, use the standard `add_job_by_url.py` pipeline:
1. Open the job posting URL in the browser
2. Run `python3 scripts/add_job_by_url.py --url <url>`
3. Report the screening result

## Reference Files

- `references/domain-discrepancies.md` — known domain corrections for Telegram-post companies

## Pitfalls

### Trust no domain from a Telegram post
Posts like @zarubezhom_jobs frequently use the company's brand name as the supposed domain, not its actual domain. Always verify by visiting the URL before reporting anything.

### No careers page ≠ no hiring
Some companies (AIBY, Readymag, Insense, Kodland) have "We are hiring" in their footer but no public job listings. They may hire via LinkedIn or direct referrals.

### Bot detection on research sources
Glassdoor, Crunchbase, and DuckDuckGo all block non-profile browsers. Use Google News RSS for risk scanning (layoffs, funding news). LinkedIn company pages are the most reliable source for headcount/industry.

### Subagent scope for large lists
When dispatching subagents for 15+ companies, limit each subagent to 1 company with clear instructions. Do NOT batch 5+ companies per subagent — they'll time out on slow/unresponsive sites.
