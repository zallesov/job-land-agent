# Sprout — AI Job Search Platform

**Status:** Discovered, signed in, tested searches. Scraper not yet built.

**URL:** https://app.usesprout.com/jobs?view=board

**Auth:** Google OAuth via Supabase (`qxkswyqmsisjdtmywnow.supabase.co`). Chrome profile already authenticated (zallesov@gmail.com).

**Architecture:**
- React SPA at `app.usesprout.com`
- Board view (`?view=board`) shows job cards in a grid layout
- Search: Job Title textbox + Location textbox + Filters + radius
- Each job card costs 1 credit to "Apply" — credit system may limit usage
- No infinite scroll — paginated or all-at-once card grid

**Search results tested (Berlin, 50mi radius):**
| Term | Cards |
|---|---|
| Backend Engineer | ~14 |
| Software Engineer | ~14 (mostly exec/director level) |
| AI Engineer | 41 |

**Sample companies found:** Personio, Langdock, Wolters Kluwer, Almedia, Circus Group, Enpal, STARK, Menlo79, Founders Factory, Buddybrand, Green Fusion

**Scraper plan:** Same CDP pattern as other scrapers — `connect_over_cdp` → navigate → type search terms → collect cards. Needs:
1. Handle credit system (viewing jobs may be free; applying costs credits)
2. Parse card grid (different DOM structure than WellFound/Greenhouse/JobLeads)
3. Add to `pipeline_config.json` as source `sprout`

**Pipeline integration:** Add to `config/pipeline_config.json`:
```json
{
  "name": "sprout",
  "skill": "sprout-scraper",
  "script": "scripts/scrape_sprout.py",
  "locations": ["berlin"],
  "titles": ["Software Engineer", "AI Engineer", "Engineering Manager"]
}
```
