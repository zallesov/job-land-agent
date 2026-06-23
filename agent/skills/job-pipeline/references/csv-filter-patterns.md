# Profile-Based CSV Filtering — Reference Patterns

When importing jobs from a spreadsheet, write a filter script in `tmp/`. Key patterns:

## Emoji-stripping for country strings

CSV country column often has flag emojis. Strip them:
```python
import re
clean = re.sub(r'[^\x20-\x7E]', '', country).strip().lower()
```

## Seniority detection

Use compiled regex for cleaner matching:
```python
SENIORITY_KW = re.compile(r'\b(senior|staff|principal|lead|architect|head\s+of|director|manager|sr\.?\b)', re.I)
if not SENIORITY_KW.search(title):
    # Check Experience Level column
    if exp_level not in ('senior', 'lead', 'manager', 'director', 'executive'):
        drop(...)
```

## Non-SWE title exclusion

```python
EXCLUDE_TITLE = re.compile(r'''
    \b(qa|test(ing)?\s*(engineer|analyst|specialist|manager|lead)|quality\s*(assurance|engineer|analyst|specialist|manager))
    |\b(sales\s*engineer|solutions\s*engineer|field\s*(service|application|engineer)|customer\s*(engineer|success|support))
    |\b(medical\s*coder|biostatistician|statistical\s*programmer)
    |\b(lift|escalator|stairlift|elevator)\s*(engineer|repair)
    |\b(mechanical|structural|civil|electrical|plumbing|hvac|supply\s*chain)
    |\b(magento|wordpress|drupal|joomla|salesforce)\s*(developer|engineer|architect|specialist)
''', re.I | re.VERBOSE)
```

## Salary parsing

```python
def parse_salary(val):
    if not val: return None
    val = val.strip().replace(",", "").replace("$", "").replace("€", "").replace("£", "")
    try: return int(float(val))
    except: return None
```

## Per-provider: csvfeed scrape_jobs.py structure

```python
def scrape_jobs(cdp_url, titles=None):
    jobs = []
    with open(CSV_PATH, 'r', newline='') as f:
        for row in csv.DictReader(f):
            jobs.append(ShallowJob(
                provider="csvfeed",
                title=row['Title'],
                company=row['Company Name'],
                url=row['Apply Url'],
                location=row['Country'],
                country=_clean_country(row['Country']),
                dedup_key=f"{row['Company Name']}::{row['Title']}",
                salary_raw=_build_salary(row),
                status="new",
            ))
    return jobs
```

## Post-ingest enrichment from CSV

After ingest, job descriptions from the CSV must be written to the DB. Match by URL:

```bash
echo '{"title":"...","description":"...","location":"...","salary_range":"..."}' | \
  python3 scripts/db_write_job_fields.py --job-id <ID>
```

Truncate descriptions to 3000 chars to match `enrich_job.py`'s limit.
