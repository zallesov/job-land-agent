# Tag Keyword False Positive Bug (May 2026)

## The Bug

In `scripts/tag_new_jobs.py`, the `ROLE_KEYWORDS` dict for `engineering_manager` included the keyword `"em "`:

```python
"engineering_manager": ["engineering manager", "em ", "head of engineering", "vp engineering"],
```

The classifier runs `f"{title} {description}".lower()` and checks `any(k in text for k in kws)`. `"em "` appears as a substring in:

- "Software Engineer" → softwar**em **... — no. But "System" → syst**em ** and "problem" → probl**em ** do match.
- Every title containing "Engineer" followed by a description word starting with "m" also matches.

## Impact

17 out of 25 jobs tagged `engineering_manager` were false positives (68%). Examples:

- "Enterprise Account Executive"
- "Senior Software Engineer, MediaWiki"
- "Staff Software Engineer"
- "Cloud AI API Integrations – Subject Matter Expert"
- "EMEA Enterprise Account Executive"

All of these were caught by `"em "` matching "EM" in "EMEA", "em" in "System"/"problem" in the description, or "em" in "Software Engineer" combined with description text.

## The Fix

Replaced `"em "` with multi-word keywords that can't match incidentally:

```python
"engineering_manager": [
    "engineering manager", "engineering lead", "engineering director",
    "head of engineering", "vp of engineering", "vp engineering",
    "director of engineering", "eng manager", "eng lead",
],
```

After fix: FPs dropped to 3 of 10 (30%). Remaining FPs are from descriptions mentioning roles like "director of engineering" as a person the role works with — this is an inherent limitation of full-text keyword matching.

## Design Rule

**Keywords must be at least 2 full words** or anchored to relevant context. Single words and two-character keywords cause massive false positives. When adding keywords, run `classify()` against a representative sample of real job titles from the DB to validate.
