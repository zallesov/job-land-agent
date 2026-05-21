# nano-pdf troubleshooting

## What the tool actually does

`nano-pdf` is not a text-native PDF editor. It:
1. renders a PDF page to an image,
2. sends the page image plus style references and prompt text to Gemini image generation/editing,
3. receives a generated image,
4. OCRs the result back into a PDF page.

Implications:
- Best for style-preserving page rewrites, title changes, and small content edits.
- Less deterministic than generating a fresh PDF from markdown/HTML.
- For resumes, use it when preserving the original design matters more than exact text layout fidelity.

## Common failure modes

### `GEMINI_API_KEY not found in environment variables`
Set `GEMINI_API_KEY` explicitly in an env file or shell environment before running `nano-pdf`.

### `API key not valid`
If the key is stored in `.env`, ensure the line contains only the raw value:

```env
GEMINI_API_KEY=AIzaSy...
```

Do not append inline comments on the same line, e.g. avoid:

```env
GEMINI_API_KEY=AIzaSy...  # alias for GOOGLE_API_KEY
```

Some simple `.env` parsing paths will treat the inline comment as part of the key.

### Missing system dependencies
On macOS, install:

```bash
brew install poppler tesseract
```

`nano-pdf` checks for `pdftotext` and `tesseract` before editing.

## Prompting pattern for resume updates
When editing an existing resume PDF, include constraints like:
- preserve original visual design and typography hierarchy,
- keep it a resume, not a redesigned poster,
- maintain ATS-friendly readability,
- prefer wording compaction over layout changes,
- keep existing contact formatting where possible,
- explicitly provide the exact replacement content for the target page.

## Practical recommendation
If multiple pages need substantial rewriting, or exact text fidelity matters more than style preservation, prefer generating a fresh clean PDF from markdown/HTML instead of forcing `nano-pdf` to rewrite every page image.
