# nano-pdf notes from Zall resume session

Context:
Tried to update an existing 4-page resume PDF while preserving visual style, then converged on a regenerated markdown-driven PDF because consistency mattered more than style preservation.

What mattered
- The user wanted the original PDF style reused if possible, but rejected inconsistency between pages.
- The reliable solution was to regenerate from markdown with one consistent font system.

nano-pdf specifics observed
- The installed package uses Gemini image generation/editing (`gemini-3-pro-image-preview`) under the hood.
- It requires `GEMINI_API_KEY` specifically.
- A valid key can still fail if the backing project has no billing/quota for image generation.
- Inline comments on the same env line break raw key parsing, e.g. avoid:
  - `GEMINI_API_KEY=...  # comment`
- Better:
  - `# comment`
  - `GEMINI_API_KEY=...`

Workarounds that helped
- Installed missing local dependency: `poppler` (for `pdftotext` / render pipeline)
- Enabled `PIL.ImageFile.LOAD_TRUNCATED_IMAGES = True` in nano-pdf runtime to get past truncated-image failures
- Reduced nano-pdf render resolution from `2K` to `1K` for stability

Verification lessons
- Do not trust successful PDF creation alone
- Always check:
  - file existence
  - page count
  - extracted text quality
  - page-to-page consistency
- In this session, nano-pdf produced a file but page 2 quality was poor and fonts were inconsistent, so a clean regenerated PDF was preferable

Decision rule reinforced
- For job-application resumes, use markdown as the source of truth and generate a fresh ATS-safe PDF unless exact legacy styling is more important than determinism
