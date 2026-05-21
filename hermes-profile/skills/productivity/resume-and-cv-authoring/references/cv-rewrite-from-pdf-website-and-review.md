# CV rewrite from PDF + website + recruiter review

Use case
- User has an existing PDF resume/CV
- User also has a personal website with broader career material
- A recruiter/ATS service produced generic feedback
- User wants a final CV draft suitable for PDF generation

Pattern
1. Extract facts from the PDF and preserve exact metrics where possible.
2. Read the website for stronger positioning themes, additional projects, and missing context.
3. Classify recruiter feedback into:
   - apply directly
   - soften
   - ignore
4. Draft a master content inventory if needed, but do not stop there.
5. Produce the exact final-ready CV text in markdown/plain text.
6. Expect user corrections on:
   - title normalization
   - how specific the skills section should be
   - split tenures / multiple date ranges
7. Update the draft quickly to reflect those preferences.

Specific lessons from this session
- A senior engineering candidate with ~20 years of experience should target 2 pages, not 1.
- ATS feedback about adding a dedicated skills section is useful.
- Street address is unnecessary; city/region + contact details are enough.
- If the user says the output should be the exact content for the PDF, switch immediately from planning mode to final-copy mode.
- If the user prefers a broad/non-technical skills section, rewrite Core Skills at the capability level instead of listing exact tools.
- If the original CV accurately represents split tenures (for example one company before and after an intervening role), keep that structure in the final draft rather than flattening it.
- If the user prefers an unusual title like "Chief of Everything," preserve it.

Suggested checklist before finalizing
- Summary is 50–90 words
- Skills section exists and matches desired specificity
- Dates are month/year and reverse-chronological
- Recent roles have strongest bullets
- Older roles are compressed
- Projects are optional, not required
- Final text reads like resume copy, not workshop notes
- Open factual placeholders are explicit
