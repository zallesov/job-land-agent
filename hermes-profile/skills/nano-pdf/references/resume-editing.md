# Resume PDF editing with nano-pdf

Use this when the goal is to update wording in an existing resume/CV PDF while preserving the original visual style.

## Recommended workflow

1. Prepare the exact final resume wording in a markdown or text file first.
   - Do not improvise content inside the nano-pdf prompt.
   - Resolve titles, dates, skills wording, and section order before editing the PDF.

2. Use the existing PDF as the visual baseline.
   - Treat it as a style-preservation task, not a redesign task.
   - Edit only the page(s) that need wording changes.

3. Pass style references from the untouched pages.
   - Example:
     ```bash
     nano-pdf edit resume.pdf 1 "<prompt>" --style-refs 2,3,4 --output resume-updated.pdf
     ```
   - This helps preserve typography hierarchy, spacing, and color cues.

4. In the prompt, explicitly state:
   - preserve original visual design
   - preserve typography hierarchy and spacing style
   - keep ATS readability
   - prefer slight wording compaction over layout changes
   - do not redesign the document

5. For multi-page resumes, edit page by page.
   - Put page-specific target content in each prompt.
   - Avoid trying to rewrite the whole document in one giant instruction.

6. Verify the result.
   - Open the output PDF visually.
   - Confirm page count.
   - Re-run text extraction if ATS readability matters.

## Practical notes

- Current package behavior expects `GEMINI_API_KEY` in the environment.
- On macOS, install dependencies first:
  ```bash
  brew install poppler tesseract
  ```
- If a split tenure or unusual date range exists, include the exact final date text in the prompt instead of assuming the model will preserve it correctly.
- Normalize the content before editing the PDF; nano-pdf should apply wording, not decide resume strategy.
