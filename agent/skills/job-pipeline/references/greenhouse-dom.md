# Greenhouse DOM Card Structure

## Current Card Layout (May 2026)

Each job card is a div with class `flex flex-col p-6 gap-4 justify-between border-2 rounded-lg border-solid border-gray-00 bg-white` containing:

```
<div class="flex flex-col p-6 gap-4 ...">
  <h4 class="section-title line-clamp-2">  ← job title
  <div class="flex flex-row items-center gap-2"> ← company name
    ...
  </div>
  <div>...</div>  ← location chips
  <div class="flex flex-row items-center justify-between">  ← posted date + link
    <p class="body body__secondary">Posted yesterday</p>
    <a class="btn btn--rounded btn--medium" href="...">View job</a>
  </div>
</div>
```

## The `resultContainer()` Bug

The scraper's `collect_greenhouse()` JS function `resultContainer()` walks up from the anchor element (the "View job" link) and looks for the first ancestor whose `innerText` contains both "Posted " and "View job" and is under 900 chars.

**Problem:** The anchor's immediate parent (the posted-date row div) satisfies all three conditions — it's a tiny div with just "Posted yesterday\n\nView job" (~30 chars). So `resultContainer()` returns this row, which has no title or company name.

**Fix (applied 2026-05-23):** Added `text.length > 100` to the condition so the tiny row div is skipped and the walk climbs to the full card div.

```javascript
// Before (broken):
if (text.includes('Posted ') && text.includes('View job') && text.length < 900)

// After (fixed):
if (text.includes('Posted ') && text.includes('View job') && text.length < 900 && text.length > 100)
```

## How to Debug if Jobs Show 0 Extracted Again

1. Navigate to the for-you feed URL in Chrome
2. In console: `document.querySelector('main').innerHTML.substring(0, 2000)` to see card structure
3. Find the card container class and check if `resultContainer()` reaches it
4. The anchor's `innerText` should be just "View job" — the title is in a sibling `<h4>`, not inside the link
5. If the card layout changed again, adjust `resultContainer()`'s walk-up criteria or rewrite the extraction to use `document.querySelectorAll('h4.section-title')` and walk to parent card
