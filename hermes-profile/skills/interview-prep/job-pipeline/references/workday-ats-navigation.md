# Workday ATS Navigation Pattern

Workday career portals are JS-heavy single-page apps. The headful browser handles them well, but navigation differs from standard websites.

## Finding the ATS URL

Company careers pages often have a "View Open Opportunities" button that opens a new tab. The `<a>` tag may not show the Workday URL in its href.

**Use browser_console to find it:**
```js
document.querySelectorAll('a').forEach(a => {
  if (a.textContent.includes('View Open')) console.log(a.href);
});
```

Common Workday portal URLs:
- `https://<company>.wd5.myworkdayjobs.com/<company>`
- `https://<company>.wd1.myworkdayjobs.com/<company>`

## Searching Within Workday

Workday loads jobs asynchronously. The search input is usually a `<textbox>` element in the accessibility tree.

1. `browser_type(ref, "search term")` on the search box
2. `browser_click(ref)` on the Search button
3. Wait for results to update — `browser_snapshot()` will show updated count

## Reading Job Listings

Workday renders job cards as `<li>` elements. Each card has:
- Heading with job title
- Description list with location, time type, posted date
- A `<span>` with the requisition ID (JR######)

Click a job title link to open the detail page for the full description.

## Handling "0 Jobs Found"

When a role was on an external aggregator (JobLeads, indeed) but no longer on the company's Workday, it's likely expired or filled. Note this in the assessment.

## Example: Progyny

- Careers page: `https://progyny.com/careers/`
- Workday portal: `https://progyny.wd5.myworkdayjobs.com/progyny`
- 23 open positions (as of May 19, 2026)
- "Commercial Director, Global" was NOT listed — likely expired from external aggregator
