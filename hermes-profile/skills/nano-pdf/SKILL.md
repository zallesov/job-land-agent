---
name: nano-pdf
description: "Edit PDF text/typos/titles via nano-pdf CLI (NL prompts)."
version: 1.0.1
author: community
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [PDF, Documents, Editing, NLP, Productivity]
    homepage: https://pypi.org/project/nano-pdf/
---

# nano-pdf

Edit PDFs using natural-language instructions. Point it at a page and describe what to change.

## Prerequisites

```bash
# Install with uv (recommended — already available in Hermes)
uv pip install nano-pdf

# Or with pip
pip install nano-pdf
```

System dependencies:

```bash
# macOS
brew install poppler tesseract

# Ubuntu/Debian
sudo apt-get install poppler-utils tesseract-ocr
```

API requirements:

- `nano-pdf` is Gemini-specific in practice — it uses Google's `google-genai` client and calls `gemini-3-pro-image-preview`
- Set `GEMINI_API_KEY` in the environment before running it
- Image editing/generation may require a paid Google AI Studio / Gemini key with billing enabled

## Usage

```bash
nano-pdf edit <file.pdf> <page_number> "<instruction>"
```

## Examples

```bash
# Change a title on page 1
nano-pdf edit deck.pdf 1 "Change the title to 'Q3 Results' and fix the typo in the subtitle"

# Update a date on a specific page
nano-pdf edit report.pdf 3 "Update the date from January to February 2026"

# Fix content
nano-pdf edit contract.pdf 2 "Change the client name from 'Acme Corp' to 'Acme Industries'"
```

## Notes

- Page numbers are 1-based in the current CLI (`nano-pdf edit file.pdf 1 "..."` edits page 1)
- Always verify the output PDF after editing, ideally both visually and by extracting text from the result; a command can succeed while later pages still drift or garble
- The tool uses Gemini image generation/editing under the hood and requires `GEMINI_API_KEY`
- `GOOGLE_API_KEY` alone is not enough for the current package implementation; set `GEMINI_API_KEY` explicitly
- If you load the key from a `.env` file manually, keep it on a bare line with no trailing inline comment (`GEMINI_API_KEY=...`) — naive parsing will include comment text and the API will reject the key as invalid
- A valid Gemini key can still fail with `429 RESOURCE_EXHAUSTED` if the backing Google project lacks billing-enabled quota for `gemini-3-pro-image`; this tool depends on image-generation quota, not just text-model access
- For style-preserving resume edits, use the original PDF as the baseline, pass a few unedited pages as style references, and prefer smaller runs (1–2 pages at a time)
- If you hit `image file is truncated` during generation, retry at lower resolution (for example `--resolution 1K`) and/or with fewer pages in one run
- Works best for small text changes or limited page rewrites; complex layout modifications may need a different approach
- See `references/troubleshooting.md` for dependency checks, API-key pitfalls, and resume-specific prompting guidance, plus `references/gemini-runtime-notes.md` for a real multi-page resume-edit run
