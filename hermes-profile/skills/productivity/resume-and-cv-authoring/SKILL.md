---
name: resume-and-cv-authoring
description: "Full resume/CV workflow: draft, tighten, and tailor ATS-friendly content from source materials, then generate and verify PDFs for job applications. Covers content authoring, PDF generation (markdown-driven and nano-pdf style-preserving paths), and output verification."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [resume, cv, ats, recruiting, interview-pipeline, career]
---

# Resume and CV Authoring

Create recruiter-friendly, ATS-safe resume/CV content from messy source inputs: existing PDFs, personal websites, LinkedIn-style bios, recruiter assessments, and user corrections.

Use this skill when:
- The user wants to improve a resume/CV for more interviews
- Source material exists across multiple places (PDF, website, notes)
- The user wants exact final wording, not just advice
- Recruiter or ATS feedback needs to be applied to a rewrite

## Core workflow

1. Extract and compare sources
- Pull text from the current resume/CV
- Review website/profile copy if available
- Identify overlap, contradictions, and stronger phrasing from each source
- Preserve verified metrics and employer-brand signals

2. Decide the document goal before drafting
- Default to a 2-page ATS-friendly resume for experienced engineers
- Prioritize current target roles over biography completeness
- Keep recent roles detailed; compress older roles aggressively

3. Produce the actual resume wording early
- If the user asks for CV content, do NOT stop at planning notes, content inventories, or meta-structure
- Deliver exact final-ready copy in markdown/plain text that can go straight into the PDF
- Use notes/master-draft files only as an internal intermediate when genuinely useful, then follow immediately with the actual copy

4. ATS-safe structure
- Header with name, location, website, LinkedIn, email, phone
- Sharp role-specific headline
- 50–90 word summary
- Dedicated skills section
- Reverse-chronological experience with month/year dates
- Education
- Optional compact projects/additional experience only if space allows

5. Bullet-writing rules
- Lead with outcomes and impact, not generic responsibilities
- Prefer 3–4 bullets for recent roles, 1–3 for older ones
- Keep strong metrics (cost reduction, delivery speed, test coverage, scale)
- Remove decorative claims, repeated stack lists, and founder-story sprawl
- Normalize quirky titles only if the user wants that; otherwise preserve their preferred title

## User preference learned
- For resume/CV tasks, this user prefers exact final-ready copy over planning notes or meta outlines.
- If a first pass creates a strategy document, follow quickly with the actual resume text intended for the PDF.
- Preserve user-chosen role titles when they explicitly request them (for example, keep unusual founder titles if the user prefers authenticity over normalization).
- Core Skills can be phrased more generally when the user wants less technology-specific wording.

## Handling recruiter/ATS feedback
Apply the useful parts, but do not follow generic advice blindly.

Usually keep:
- 2-page limit for senior candidates
- Dedicated skills section
- Cleaner ATS layout
- Reverse chronology
- Month/year dates

Usually soften or reject:
- One-page requirement for very experienced candidates
- Street-address requirements
- Generic critiques that are contradicted by the actual resume

## Common pitfalls
- Spending too long on analysis before producing final copy
- Making the website tone too broad or marketing-heavy for the resume
- Duplicating project details across experience and side-project sections
- Keeping too many exact technologies in the Skills section when the user wants higher-level positioning
- Quietly “improving” titles against the user’s stated preference

## Output pattern
When asked for a CV rewrite, aim to produce:
1. Exact resume-ready markdown/text
2. A short list of open factual questions (dates, title variants, contact placeholders)
3. Then a final tightened version once the user resolves those questions

## PDF Generation and Verification

Once content is finalized, generate a clean application-ready PDF. Prefer deterministic markdown-driven generation over style-preserving PDF editing whenever consistency, ATS-readability, or font/layout reliability matters.

### Canonical source files
- Keep one markdown file as the source of truth
- Keep one PDF as the current application artifact
- Reuse consistent filenames/paths across iterations

### Deterministic PDF generation (preferred path)

Generate the PDF directly from markdown when consistency matters:

- One font family across all pages
- Tight but readable spacing
- 2-page target for senior candidates unless the user explicitly wants otherwise
- ATS-friendly single-column layout
- Predictable section order: Name/Contact → Headline → Summary → Core Skills → Professional Experience → Additional Experience (optional) → Education → Selected Technologies (optional)

### nano-pdf style-preserving path (secondary, best-effort)

nano-pdf is an image-editing workflow (renders pages to images, sends to Gemini image generation, rehydrates with OCR). It is **not** a deterministic text-layout editor.

**When to use it** — only if ALL of:
- User strongly wants original PDF style preserved
- Billing/quota is available (`GEMINI_API_KEY` with image generation quota)
- Result will be visually inspected and text-verified afterward

**Operational notes:**
- Remove inline comments from `GEMINI_API_KEY=...` lines in `.env`; tools that parse raw env values may treat trailing comments as part of the key
- If image-loading errors appear (`image file is truncated`), enable `PIL.ImageFile.LOAD_TRUNCATED_IMAGES = True` in the nano-pdf runtime
- Lowering render resolution (e.g., 2K → 1K) can improve stability
- Requires `poppler` for `pdftotext` / render pipeline

**Common nano-pdf failure modes:** page-to-page font inconsistency, OCR corruption, garbled text on specific pages. If any of these occur, fall back to deterministic markdown-driven generation.

### Verification checklist

Before calling the resume finished:
- File exists
- Page count is correct
- Text extraction is clean enough to confirm legibility
- No page-specific font mismatch
- No obvious OCR corruption
- Markdown source and PDF reflect the same content

### Decision rule

For job-application resumes: use markdown as the source of truth and generate a fresh ATS-safe PDF unless exact legacy styling is more important than determinism.

## References
- See `references/cv-rewrite-from-pdf-website-and-review.md` for a worked pattern combining PDF extraction, website positioning, recruiter feedback, and user preference corrections.
- See `references/nano-pdf-notes.md` for session-specific nano-pdf behavior, quota requirements, and verification lessons from a real resume update session.
