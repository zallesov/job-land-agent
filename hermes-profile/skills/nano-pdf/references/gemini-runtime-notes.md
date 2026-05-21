# Gemini runtime notes for nano-pdf

Condensed notes from a real resume-editing session.

## What the package actually does
- `nano-pdf` is not a text-layer PDF editor.
- It renders target pages to images, sends them to Gemini image generation/editing, then OCRs the generated images back into PDF pages.
- Current package code uses Google's `genai` client and `gemini-3-pro-image-preview`.

## API key / billing pitfalls
- The package reads `GEMINI_API_KEY` directly.
- A line like `GEMINI_API_KEY=...  # comment` can break if you parse `.env` manually by splitting on `=` and using the rest verbatim.
- Even with a valid key, Google can return `429 RESOURCE_EXHAUSTED` if the project has no billing-enabled quota for Gemini image generation.
- Text-model access does not imply image-generation quota.

## Resume-edit prompting pattern that helped
- Use the original resume PDF as the baseline.
- Tell the model explicitly to preserve visual design, typography hierarchy, spacing, palette, and ATS readability.
- For multi-page resumes, create one prompt per page rather than one giant global prompt.
- Pass a few unedited pages as style references.
- Ask the model to keep the page as page 1 / page 2 of a polished 2-page resume, not a redesign.

## Reliability notes
- Editing two pages in one run at higher resolution initially failed with `image file is truncated`.
- Lowering resolution to `1K` allowed the run to complete.
- A successful command does not guarantee a good result; page 1 can be acceptable while page 2 still degrades or becomes garbled.
- Always validate with both visual inspection and `pdftotext -layout` (or similar text extraction).

## Practical guidance
- Start with 1 page if quality matters a lot.
- If you must do multiple pages, keep the batch small.
- Prefer this tool for style-preserving edits where some artifact risk is acceptable.
- For a critical ATS resume, a fresh deterministic PDF generation pipeline may be safer than image-based editing.
