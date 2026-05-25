---
name: apply-job
description: Interactive job application flow in Hermes chat. Reads job + CV, navigates to form, detects video/voice requirements (with speech outline), interviews user for cover letter material, generates 3 CL options, fills form in headed Chrome, reports filled/unfilled fields. Does NOT click submit.
---

# Apply Job

## Trigger

Activated when user says: `apply for job #N`, `apply to [company]`, `apply job_id=N`, or similar in chat.

Extract `job_id` from the message before doing anything else.

## Execution Rules

- **This is an interactive skill.** Ask questions in chat. Wait for answers. Do not proceed without user responses.
- **CRITICAL: Do NOT click the submit button under any circumstances.** Not Submit, Apply, Send, or any similar button.
- The browser MUST be visible (headed). Always use `headless=False`.
- Do NOT write SQL directly to the database.
- Phone number and salary expectation come from the CV, not from user.yaml.

---

## Phase 1: Read job, config, and CV

```bash
python3 -c "
import sqlite3, json, sys, yaml
db = yaml.safe_load(open('config/user.yaml')).get('db_path', 'jobs.db')
con = sqlite3.connect(db)
con.row_factory = sqlite3.Row
row = con.execute('''
    SELECT j.id, j.title, j.posted_company_name, j.apply_url, j.url, j.description,
           ja.apply_verdict, ja.one_line_summary
    FROM jobs j
    LEFT JOIN job_assessments ja ON ja.job_id = j.id
    WHERE j.id = ?
''', (<job_id>,)).fetchone()
if not row:
    print('ERROR: job not found', file=sys.stderr)
    sys.exit(1)
print(json.dumps(dict(row)))
con.close()
"
```

Capture: `title`, `posted_company_name`, `apply_url` (fallback to `url`), `description`.

Read user config:

```bash
python3 -c "
import yaml, json
d = yaml.safe_load(open('config/user.yaml'))
u = d['user']
print(json.dumps({
    'name': u['name'],
    'email': u['email'],
    'linkedin_url': u['linkedin_url'],
    'resume_pdf_path': u['resume_pdf_path'],
    'cv_path': d['cv_path'],
    'willing_to_relocate': d.get('work_style', {}).get('willing_to_relocate', False),
}))
"
```

Read full CV and keep in context for all subsequent phases:

```bash
python3 -c "import yaml; print(yaml.safe_load(open('config/user.yaml'))['cv_path'])" | xargs cat
```

From the CV text, extract:
- Phone number (if present)
- Salary expectation (if stated)
- Location / city
- Years of experience (infer from career dates)
- Work authorization / visa status

---

## Phase 2: Navigate to form and read its structure

**Platform selection — pick the right browser backend:**

| Platform | Backend | Why |
|---|---|---|
| WellFound | `browser_cdp` (CDP to localhost:9222) | Bot detection blocks non-profile browsers. Use real cookies + fingerprint. |
| Greenhouse, Lever, Workday, Ashby (careers page) | `browser_cdp` (CDP) | Often have bot detection. |
| All others | `browser_cdp` (CDP) | This agent must always use the visible local Chrome profile. |

### CDP approach (WellFound / bot-heavy ATS)

> **Reference:** `references/wellfound-cdp-templates.md` — copy-paste CDP payloads for extraction, clicking, filling.

Check Chrome is running:
```bash
curl -s http://localhost:9222/json/version | head -1
```
If not running: tell user to run `bash start-chrome.sh`.

**Do NOT use the non-CDP navigation tool anywhere in this agent** — it routes through the wrong browser path and can silently lose cookies, visibility, or interaction state.

Steps:
1. Use `browser_cdp(method="Target.getTargets")` to find the tab with the job URL
2. If the page isn't already open, open it with `browser_cdp(method="Target.createTarget", params={"url": "<job URL>"})`, then use CDP for every interaction.
3. Click the Apply button via CDP JavaScript:
   ```
   method="Runtime.evaluate"
   target_id="<tab_id>"
   expression="(() => { const btn = [...document.querySelectorAll('button')].find(b => b.textContent.trim() === 'Apply'); if(btn) { btn.click(); return 'clicked'; } return 'not found'; })()"
   ```
4. Use `browser_cdp(method="Runtime.evaluate", target_id="<tab_id>", params={"expression": "document.body.innerText"})` to read the modal/form after it appears
5. For full form structure, extract via CDP:
   ```
   expression="(() => { const d = document.querySelector('[role=\"dialog\"]'); const labels = [...d.querySelectorAll('label')].map(l => l.textContent.trim()); const inputs = [...d.querySelectorAll('input, textarea, select')].map(el => ({tag:el.tagName, type:el.type, name:el.name, placeholder:el.placeholder, id:el.id, required:el.required})); return JSON.stringify({labels, inputs}); })()"
   ```

### Filling React-controlled inputs (WellFound, Greenhouse, etc.)

**⚠ PITFALL: Stale refs when mixing browser backends.** If you use non-CDP browser tools, then switch to `browser_cdp` for clicking, ref IDs can belong to a different browser session and resolve to "Unknown ref" errors. Use ONLY `browser_cdp(method="Runtime.evaluate", ...)` for filling. Do not use `browser_type`, `browser_click`, or `browser_snapshot` for form filling — they route through the wrong session. Use CDP DOM extraction or screenshots only to verify after filling.

React-controlled inputs ignore `.value = "..."`. Use the native setter:
```javascript
function setValue(el, val) {
  const proto = el.tagName === 'TEXTAREA' ? HTMLTextAreaElement : HTMLInputElement;
  const nativeSetter = Object.getOwnPropertyDescriptor(window[proto].prototype, 'value').set;
  nativeSetter.call(el, val);
  el.dispatchEvent(new Event('input', {bubbles:true}));
  el.dispatchEvent(new Event('change', {bubbles:true}));
}
```
For radio/checkbox: regular `.click()` works.

Read the form structure. Identify all fields:
- Text inputs: name, email, phone, location, LinkedIn, website, GitHub, salary, years of experience
- Textareas: cover letter, work experience, **screening/essay questions** (WellFound uses these instead of cover letters)
- Dropdowns / selects: work authorization, relocation, pronouns, how did you hear
- File inputs: resume/CV upload
- Checkboxes: GDPR/consent, diversity, newsletter
- Video/voice elements (see Phase 3)
- Multi-step indicators (note which page fields appear on)

---

## Phase 3: Video/voice detection

Scan the form snapshot for video or voice message requirements.

Detection signals:
- Keywords in labels/instructions: `video`, `voice`, `record`, `recording`, `introduce yourself`, `video interview`
- Platform names: `HireVue`, `Willo`, `Spark Hire`, `Vidyard`, `Loom`
- Embedded `<video>` elements, `<iframe>` with video platform src

**If video/voice requirement detected:**

1. Extract the exact prompt text shown to the applicant (e.g., "Please record a 2-minute video introducing yourself and describing your biggest engineering challenge")
2. Tell the user in chat:

> "This application requires a **[video/voice]** message:
> *[exact prompt text]*
>
> Here's a speech outline for this prompt:
>
> **Opening (30 sec):** [Hook — one concrete achievement or moment relevant to the prompt]
> **Point 1 (45 sec):** [Most relevant experience from CV + interview answers]
> **Point 2 (45 sec):** [Specific angle on this company/role]
> **Close (30 sec):** [Why this role, confident forward-looking statement]
>
> Do you want to proceed with filling the rest of the form, or skip this application?"

3. Wait for user response.
   - If **skip**: close browser, reply "Skipped. Job #<N> left as-is.", end skill
   - If **proceed**: continue to Phase 4

If no video/voice requirement: proceed directly to Phase 4.

---

## Phase 4: Screening answers (adapted to form type)

**Detect the application format:**

- **Essay/screening questions** (WellFound, Lever): No cover letter field. Instead, 3-8 custom textarea questions. Skip the Q&A interview — draft all answers immediately based on CV + job description. Present them in chat. The user edits in the form.
- **Cover letter field** (Greenhouse, Workday): Follow the interview flow below.

### For essay/screening questions

1. Extract all question labels from the form (via CDP as shown in Phase 2)
2. Draft one answer per question, mapping CV experience to the job description
3. **Tone for this user:** Short, conversational, humanized. Include 1-2 deliberate minor spelling mistakes per answer (e.g., "themselfs", "werent", "paied"). No corporate-speak. Read like a real person wrote them quickly. Avoid process/committee language — this user hates it.
4. Present all answers together in chat. The user will iterate on them (rephrase, shorten, change stories). Apply edits immediately via CDP.
5. Once user approves: use the React setter pattern (Phase 2) via `browser_cdp` to populate all textareas
6. Fill simple fields (LinkedIn, GitHub, radios, dropdowns) in the same pass
7. Do NOT click Submit

### For cover letter forms

Ask the following three questions **one at a time**. Wait for each answer before asking the next.

**Question 1:**
> "Why does this role at [Company] interest you specifically?"

**Question 2:**
> "Any recent achievement or project not on your CV that's particularly relevant here?"

**Question 3:**
> "Anything specific you want the hiring team to know?"

Record all three answers for use in Phase 5.

---

## Phase 5: Generate final text

**If essay/screening questions (no cover letter field):** Skip to Phase 6. The answers drafted in Phase 4 are the application text.

**If cover letter form:**

Using the three interview answers + job description + CV, generate three distinct cover letter options:

**Option 1 — Technical depth**
Opens with stack/architecture match. Leads with engineering specifics, system design, or technical achievements that map to the job requirements. Best when the role is IC-heavy or technically demanding.

**Option 2 — Leadership/impact**
Opens with team outcomes, scale, or organizational results. Leads with people leadership, cross-functional influence, or product impact. Best when the role involves management or senior influence.

**Option 3 — Narrative hook**
Opens with a concrete story drawn from the interview answers. The opening line should be specific and memorable. Builds out from the story to connect experience to this role.

Each option:
- 3–4 paragraphs, under 400 words
- No salutation ("Dear Hiring Manager" etc.)
- No closing signature
- Personalized to company name, role, and any details from the interview

Present all three in chat with clear labels. Then ask:

> "Pick 1, 2, or 3 — or tell me what to change."

If the user requests a revision (e.g., "rewrite #2 but shorter", "make option 1 less formal"), revise and re-present. Repeat until the user confirms a choice.

Once a cover letter is chosen, move to Phase 6.

---

## Phase 6: Fill the form

### WellFound / CDP approach

Use `browser_cdp` with `Runtime.evaluate` on the correct `target_id` (from `Target.getTargets` — find the tab with the job URL).

**Simple fields (radios, checkboxes):** Query by ID and `.click()`:
```javascript
d.querySelector('#form-input--...').click()
```

**React-controlled text fields:** Use the native setter pattern:
```javascript
function setValue(el, val) {
  const proto = el.tagName === 'TEXTAREA' ? 'HTMLTextAreaElement' : 'HTMLInputElement';
  const nativeSetter = Object.getOwnPropertyDescriptor(window[proto].prototype, 'value').set;
  nativeSetter.call(el, val);
  el.dispatchEvent(new Event('input', {bubbles:true}));
  el.dispatchEvent(new Event('change', {bubbles:true}));
}
setValue(el, 'your text here');
```

**Fill order:**
1. LinkedIn URL, GitHub URL
2. Visa/work authorization radios
3. Experience/eligibility radios
4. Essay/screening textareas (one CDP call per field is OK — batch where possible)
5. Confirm with `browser_cdp(method="Runtime.evaluate", target_id="<tab_id>", params={"expression": "document.body.innerText"})` that all values appear

**NEVER click Submit / Send application.**

### Other platforms (Greenhouse, Lever, Workday)

Build the fields file and run the filler script:

```bash
python3 -c "
import json

fields = {
    # From user.yaml
    'first_name': '<first word of name>',
    'last_name': '<remaining words of name>',
    'full_name': '<name>',
    'email': '<email>',
    'linkedin_url': '<linkedin_url>',
    'resume_path': '<resume_pdf_path>',
    'willing_to_relocate': '<willing_to_relocate>',
    'how_did_you_hear': 'Job board',
    'start_date': 'Immediately / 2 weeks notice',

    # Extracted from CV
    'phone': '<phone from CV or blank>',
    'salary_expectation': '<salary from CV or blank>',
    'years_of_experience': '<inferred from CV>',
    'work_authorization': '<from CV>',
    'location': '<from CV>',

    # Generated
    'cover_letter': '<chosen cover letter text>',
    'screening_answers': {},  # populated below for any specific form questions
}

with open('/tmp/apply_fields_<job_id>.json', 'w') as f:
    json.dump(fields, f, indent=2)
print('Fields written')
"
```

For any custom screening questions found on the form (e.g., "Why do you want to work here?", "Describe your experience with X"), add them to `screening_answers` as `{ "question_substring": "answer" }`.

Run the filler script:

```bash
python3 scripts/apply_job_filler.py \
  --apply-url "<apply_url>" \
  --fields /tmp/apply_fields_<job_id>.json \
  --job-id <job_id> \
  --report /tmp/apply_report_<job_id>.json \
  2>&1 | tee /tmp/apply_log_<job_id>.txt &
```

Wait up to 120 seconds for the report to appear:

```bash
python3 -c "
import time, os, sys
for _ in range(60):
    if os.path.exists('/tmp/apply_report_<job_id>.json'):
        sys.exit(0)
    time.sleep(2)
print('TIMEOUT: report not written', file=sys.stderr)
sys.exit(1)
"
```

Read the report:

```bash
cat /tmp/apply_report_<job_id>.json
```

---

## Phase 7: Report in chat

Report the result directly in chat. Do not send Telegram.

Format:

```
✅ Filled N fields: first_name, last_name, email, linkedin_url, phone, cover_letter, ...

⚠️  Could not fill: [list of unfilled fields]
   → Fill these manually in the open Chrome window.

🎬 Video/voice required — see speech outline above.   ← include only if video/voice was detected

⛔ Submit button NOT clicked — review the form and click Submit when ready.
```

If there were filler errors, list them under the unfilled section.

The browser window stays open. The user submits manually.

---

## Phase 8: After user confirms submission

Once the user confirms they have clicked Submit:

1. Set `user_status='applied'` in the DB:

```python
import sqlite3, yaml
db = yaml.safe_load(open('config/user.yaml')).get('db_path', 'jobs.db')
con = sqlite3.connect(db)
con.execute(
    "UPDATE jobs SET user_status='applied', updated_at=datetime('now') WHERE id=?",
    (<job_id>,)
)
con.commit()
con.close()
print(f"Set user_status=applied for job {<job_id>}")
```

2. Report in chat: "Job #<N> marked as applied."

---

## Error Handling

### apply_url inaccessible or requires login
- Try the job's `url` field as fallback
- If still blocked: "Could not open the application form — the URL may require a manual login. URL: <url>"
- End skill

### Filler script fails or times out
- Reply in chat: "The form filler encountered an error. Check `/tmp/apply_log_<job_id>.txt` for details."
- If the browser is still open, note that in the message so the user can fill manually

### Job not found in DB
- Reply: "No job found with id=<N>. Check the job ID and try again."
- End skill

### Form is multi-page
- After filling page 1, note in the report that the form has multiple pages
- The filler script handles pagination where possible; if it stops early, list remaining pages in the chat report

---

## Reminders

- NEVER click Submit, Apply, Send, or any submit-equivalent button
- Phone and salary come from the CV, not hardcoded blanks
- Cover letter must be personalized to the specific company and role using the interview answers
- The browser window must stay visible throughout (`headless=False`)
- Skip diversity/EEOC fields — do not fill
- If a "how did you hear" field exists, answer: "Job board"
