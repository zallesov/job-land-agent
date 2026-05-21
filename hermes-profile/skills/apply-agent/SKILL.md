---
name: "apply-agent"
category: "interview-prep"
author: "InterviewPrep Agent"
description: "Generic job application agent. Navigates any ATS page (Greenhouse, Lever, Workable, Ashby, Breezy, or any custom career portal), detects form fields, maps to a structured profile, and fills/submits the application using browser automation."
trigger: "When the user says 'apply for job #N' or you need to submit an application for a researched job"
version: 1.0
---

# Apply Agent

Generic browser-based job application agent. Works on any apply URL by parsing the page's form fields, mapping them to a candidate profile, and submitting.

**Do NOT hardcode ATS-specific selectors.** Instead, use generic field detection (label text matching, placeholder matching, name attribute matching) to make the agent work across any ATS platform.

## Required Inputs

The agent expects these to exist before running:

```
profile: /Users/zall/interviews/profile.json
resume: /Users/zall/interviews/ALEKSANDR_ZALESOV-CV-05.2026.pdf
```

The `profile.json` should contain:
- `basics` — name, email, phone, location, pronouns
- `links` — linkedin, github, website
- `current_employment` — company, title, compensation, notice_period
- `work_authorization` — eu_eligible, us_eligible, visa_sponsorship_required, notes
- `resume_path` — absolute path to resume PDF

## Flow

### Step 1: Preconditions

```
Check the job in DB:
  - Job exists and status != 'applied'
  - apply_url is present
  - profile.json exists
  - resume PDF exists
```

If job is already applied, abort with status.

### Step 2: Navigate + Detect Apply Button

Navigate to apply_url. Check the page for:

1. **Already-applied state**: look for text like "You have applied", "Already applied", "Application submitted" — abort if found.
2. **Apply button**: look for a link/button with text containing "apply" (case-insensitive). Click it to reveal the form.
3. **External redirect**: if clicking doesn't reveal a form but redirects to another page, follow the redirect.

After clicking apply, take a **browser_snapshot(full=true)** to get the full form.

### Step 3: Inventory All Form Fields

Read the full form HTML via `browser_console(expression='document.getElementById("application-form")?.outerHTML || document.querySelector("form")?.outerHTML')`.

Classify each field into one of:

| Type | Detection | Handler |
|------|-----------|---------|
| file/upload | input type="file" or styled upload zone with "upload"/"attach"/"resume" in label | Upload resume PDF |
| single-line text | input type="text" or input without type | Fill from profile match |
| email | input type="email" | Fill email from profile |
| tel/phone | input type="tel" or field with "phone" in label | Fill phone from profile |
| textarea | textarea element | Fill from profile or generate answer |
| radio | input type="radio" grouped under a question | Select best match from profile |
| checkbox | input type="checkbox" | Check matching options |
| dropdown/select | select element | Select matching option |
| hidden | input type="hidden" | Skip |
| captcha | h-captcha, g-recaptcha, cf-turnstile | Flag as manual-intervention required |

### Step 4: Map Fields to Profile

For each visible form field (not hidden), use the field's label text to find a match in the profile. Use fuzzy matching:

Priority order for field matching:
1. Match by label text contains keyword
2. Match by placeholder text
3. Match by name attribute
4. Match by aria-label attribute

Field-to-profile mapping:

| Label keywords | Profile field |
|---|---|
| resume, cv, upload, attach | Upload resume path |
| full name, name, your name | basics.name |
| email, e-mail | basics.email |
| phone, telephone, mobile, phone number | basics.phone |
| location, current location, city | basics.location |
| company, current company, organization | current_employment.company |
| linkedin | links.linkedin |
| github | links.github |
| website, portfolio, personal site | links.website |
| compensation, salary, current compensation | current_employment.compensation |
| notice period, notice | current_employment.notice_period |
| designation, title, job title, current title | current_employment.title |
| work authorization, work authorisation, legally authorised, visa, sponsorship | work_authorization |
| pronouns | basics.pronouns |
| cover letter, why you, why this role | Generate from job assessment |

### Step 5: Field Handlers

**Text inputs:** Use `browser_type(ref, value)` to fill the field. Always verify the value persisted afterwards via `browser_console` — some ATS fields (notably Lever's location) swallow the value.

**Lever-style location field:** Lever uses `#location-input` with a hidden `#selected-location` input and an autocomplete dropdown. `browser_type()` on the ref clears the autocomplete's internal state. Strategy: after typing, use JavaScript to `document.querySelector('#location-input').dispatchEvent(new Event('blur', {bubbles: true}))` which sometimes forces the structured location save. If that fails, the location field requires manual intervention (type in browser and select from dropdown).

**File upload:** The browser tool's `browser_click()` on a file input triggers a system file dialog which cannot be automated via the Hermes CLI browser API. `browser_console` JavaScript cannot set `<input type="file">.files` due to browser security. Workarounds:
1. Use a Python+Playwright script via `terminal()` — the Playwright API has `locator.setInputFiles(path)` which bypasses the file dialog.
2. If the file input is hidden behind a styled button (common pattern), make it visible first via JS (`element.style.display = 'block'; element.style.visibility = 'visible'`), then flag for manual upload.
3. Accept the limitation: fill all text fields, flag the file upload for the user, and let them upload before submitting.

**Radio buttons and checkboxes:** `browser_click(ref)` on the label ref works inconsistently on Lever — the click succeeds but the radio value may not register. **More reliable approach:** use JavaScript to click the input element directly:

```javascript
// Instead of browser_click on the label ref:
var radio = document.querySelector('[name="FIELD_NAME"][value="VALUE"]');
if (radio) radio.click();
```

Verify selection after clicking: `document.querySelector('[name="FIELD_NAME"]:checked')?.value`.

For Lever's custom card radios (named `cards[...][fieldN]`), the name attribute contains special characters — use CSS attribute selector syntax: `document.querySelector('[name="cards[UUID][field1]"][value="30 days or less"]')`.

**Textarea (free text questions):** Read the question text and generate a suitable answer using the job assessment's `one_line_summary` and `assessment_notes` from the DB. After setting `.value`, dispatch both `input` and `change` events:

```javascript
ta.value = '...';
ta.dispatchEvent(new Event('input', {bubbles: true}));
ta.dispatchEvent(new Event('change', {bubbles: true}));
```

**Captcha:** If the form has hCaptcha, reCAPTCHA, or Cloudflare Turnstile:
1. Fill all other fields
2. Take a screenshot
3. Inform the user a captcha requires manual intervention
4. Ask user to solve and submit

### Step 6: Submit

Before submitting, take a screenshot and show to the user for review. Ask to confirm. If confirmed, click submit.

### Step 7: Log Result

Insert into applications table. Schema (check first with `.schema applications`):

```sql
INSERT INTO applications (job_id, status, submitted_at, updated_at, application_notes_path)
VALUES (?, 'applied', datetime('now'), datetime('now'), 'Submitted via apply-agent');
```

Error states:
- `applied` — submission confirmed successful (page showed "thank you", "submitted", "received")
- `apply_failed` — submission returned validation errors or errored out; write the error text to the `error` column
- `apply_intervention` — captcha or manual step blocked full automation; the form was filled but not submitted

Use `status='draft_requested'` (the default) when the user just requested an application and it hasn't been submitted yet. Update to `applied` when the submission is confirmed.

## Pitfalls

1. **Already-applied state detection** — check static text like "You have already applied" before starting. Also check for disabled submit buttons or "Application submitted" headers.
2. **Multi-page forms** — Greenhouse has "Next" buttons with hidden subsequent sections. Always check for a visible "Next" button after filling each page section.
3. **Radio button clicks via `browser_click` on labels may not register** — Use `browser_console` to `.click()` the input element directly instead of relying on the label ref. Verify selection afterwards.
4. **Lever's location field swallows typed values** — The structured location autocomplete (`#location-input`) clears programmatic `value=` assignments. Try dispatching `focus`, `input`, `change`, `blur` events. If that fails, flag for manual intervention.
5. **File upload requires Playwright API** — The Hermes browser tool cannot `setInputFiles`. Use a Python+Playwright script via `terminal()` for automated upload, or flag for the user.
6. **hCaptcha/reCAPTCHA requires manual intervention** — Always flag for the user. Never attempt auto-solving.
7. **LinkedIn auto-fill button** — Ignore it. Fill fields manually. Don't click social login buttons.
8. **Rate limiting** — Max 3 applications per session. Lever/Greenhouse can rate-limit on rapid submissions.
9. **Form validation after submit** — The page may show inline errors without navigating away. Check for `.error-message`, `.validation-error`, or `[aria-invalid="true"]` elements after submission.
10. **Required-asterisk detection** — Fields with `<span class="required">✱</span>` are mandatory. The snapshot shows these clearly.
11. **Form state verification** — After each fill operation, verify the value persisted via `browser_console`. `browser_type` claims success but the value may not stick (location field, some textareas with custom event handlers).
