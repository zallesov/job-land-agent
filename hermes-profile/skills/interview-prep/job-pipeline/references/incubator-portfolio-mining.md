# Incubator & VC Portfolio Mining

A job discovery strategy: scrape a VC/incubator portfolio page, filter by location, batch-research every company for remote engineering roles.

## When to use

- User has identified an incubator/VC with a Berlin/Germany presence (Antler, YC, Techstars, etc.)
- The portfolio page has a filterable directory (location, sector, year)
- User wants exhaustive coverage: research ALL companies, not a hand-picked subset

## Flow

### 1. Scrape the portfolio directory
- Navigate to the portfolio page with location filter (e.g., `?location=Germany`)
- Extract company names, sectors, years, and descriptions
- Target: all companies, not just the visible ones — click "Load more" if paginated

### 2. Batch-create research tickets via Kanban
- One ticket per company, assigned to `interviewprep` profile
- Ticket body template:
  ```
  Company: {name}
  Sector: {sector}
  Description: {desc}
  Origin: {incubator name} {location} portfolio

  Tasks:
  1. Visit the company website and careers page
  2. Search for remote engineering/technical job postings (Staff/Principal/Senior SWE, AI/ML, Platform)
  3. If remote jobs found, create a follow-up ticket to run the job-research skill on each job URL
  4. Report findings in the completion summary
  ```
- Use a Python script with `hermes kanban create` in a loop for bulk creation

### 3. Workers autonomously research each company
- Each worker visits the company site, checks careers pages
- Searches external job boards if no careers page exists
- Creates follow-up `job-research` tickets if remote engineering roles found
- Reports "no jobs" with reason if nothing found

### 4. Aggregate results
- After batch completes, query board for tickets with children (follow-ups = jobs found)
- Two useful queries:
  - `hermes kanban list --assignee interviewprep | grep "research:"` — full board
  - Check for tickets with `children:` in `hermes kanban show <tid>` — these found jobs

## Pitfalls

- **Alumni vs current cohort**: Portfolio pages often mix early-stage (pre-revenue) with scaling companies. Pre-seed/seed startups rarely have formal engineering roles. Temper expectations: 2-5% hit rate is normal.
- **"Load more" pagination**: Some portfolio pages (Antler) load all companies via JS — the DOM may not have a clickable button and instead lazy-loads on scroll. Use browser_console to extract all visible text.
- **Remote is rare in early-stage Berlin startups**: Most Antler Berlin companies are office-first or hybrid Berlin. Don't be surprised by very low yield.
- **User expects thoroughness**: Research ALL companies, not a sample. The user will notice if you skipped some.
