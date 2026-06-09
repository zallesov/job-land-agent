# Domain Discrepancies: Telegram/Forum Posts vs Actual Domains

Companies from @zarubezhom_jobs and similar channels frequently use the wrong domain.
Verified in session 2026-06-08.

## AI Companies

| Listed Name | Wrong Domain | Actual Domain | Notes |
|---|---|---|---|
| **Fjor Health** (aka Formula) | fjorhealth.com | **Not found** | Both `fjorhealth.com` and `formulaco.com` don't resolve. Possibly rebranded or shut down web presence. |
| **Fluently** | fluently.so | **Blog only, no careers page** | Product may be at `app.fluently.so`. LinkedIn page unavailable. No public careers page found. |
| **Replika** | replika.com/careers | **404** | Careers page returns "Oops! Nothing here." Available on LinkedIn only. |
| **AIBY** | aiby.com/careers | **Live** | Mostly growth/marketing roles. SWE roles likely via ATS/LinkedIn. |

## B2B Companies

| Listed Name | Wrong Domain | Actual Domain | Notes |
|---|---|---|---|
| **CloudLinux** | cloudlinux.com/careers | **404** | Footer says "We're hiring!" but careers page broken. |
| **Emerging Travel Group** | emergingtravel.com/careers | **Not found** | RateHawk at `ratehawk.com`. Careers page returns 404. |
| **Readymag** | readymag.com/about | **Live** | "We are hiring" in footer but no public job listing page. |
| **Insense** | insense.com | **insense.pro** | `insense.com` is for sale (domain squatter). Actual platform at `insense.pro`. No careers page. |
| **Kodland** | kodland.com | **kodland.org** | `kodland.com` has SSL errors. Actual site at `kodland.org`. No careers page. |

## B2C Companies

| Listed Name | Wrong Domain | Actual Domain | Notes |
|---|---|---|---|
| **Prequel** | prequel.com | **prequel.app** | `prequel.com` is a domain squatter. `prequel.co` is a data export API company (unrelated). App at `prequel.app` — no careers page. |
| **Ewa** (Ewa Learn Languages) | ewa.com | **Not found** | `ewa.com`, `getewa.com`, `ewa-app.com` all dead or for sale. 60M+ users claimed but no web presence found. |

## Gamedev & Other

| Listed Name | Wrong Domain | Actual Domain | Notes |
|---|---|---|---|
| **The Open Platform** (TON) | theopenplatform.com | **Not found** | `theopenplatform.com` is parked on GoDaddy. `ton.org` is the TON blockchain foundation, not the ecosystem builder company. |
| **Tangem** | tangem.com/en/careers | **404** | Swiss company (Zug). Careers link in footer leads to 404. |

## Verified Companies (domains correct)

| Company | Domain | Careers Page | Notes |
|---|---|---|---|
| **Chess.com** | chess.com/jobs | ✅ Live | 100% remote, actively hiring SWE |
| **My.Games** | careers.my.games | ✅ Live | Remote-first, global team |
| **Playrix** | playrix.com | ✅ Live (JS-rendered) | "Work from anywhere" |
| **Owlcat Games** | owlcat.games/careers | ✅ Live | cRPG studio |
| **Sumsub** | sumsub.com/careers | ✅ Live | Remote-first, Berlin office |
| **Cosuno** | cosuno.com/en/company#careers | ✅ Live (Ashby) | Berlin-based, AI construction platform |

## Pattern Checklist for Domain Verification

When the user provides a company name from an external list:

1. Try `companyname.com` first — most likely correct
2. If DNS error / parked / wrong company → Google search
3. Check LinkedIn company page for website link
4. Handle special TLDs: `.app`, `.pro`, `.org`, `.games`
5. Flag as "domain not found" after exhausting reasonable options
6. Note the discrepancy explicitly in the report — helps the user correct their source

## Russian/English Orthography Pitfalls

- Cyrillic capital `С` (U+0421) looks identical to Latin `C` in most fonts
- Example: `Сonsuno` → search returns "Suno" (AI music), not "Cosuno"
- Fix: search both the spelled-out name and "company <name>" with Latin letters
