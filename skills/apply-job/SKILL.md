---
name: apply-job
description: Fill out a job application form in a visible (headed) browser. Reads job from DB, generates cover letter, fills all fields, uploads CV. Does NOT submit. Reports to Telegram when ready. Triggered by prompt containing "job_id=N command_id=N db=/path/jobs.db".
---

# Apply Job

## Execution Rules

- **Do NOT ask for confirmation.** Execute immediately and autonomously.
- This is a background automated task. On any blocking error, mark command failed and send Telegram alert.
- **CRITICAL: Do NOT write SQL directly to the database.** Only allowed DB write: `status='running'` in Step 1. Use `db_mark_apply_done.py` in Step 6.
- The browser MUST be visible (headed). Use `headless=False` in all Playwright calls.
- Do NOT click the submit button under any circumstances.

## Input

Prompt contains: `job_id=<N> command_id=<N> db=<path>`

Parse these three values before doing anything else.

---

## Step 1: Mark command running + read job

```bash
python3 -c "
import sqlite3, json, sys
db = '<db_path>'
con = sqlite3.connect(db)
con.row_factory = sqlite3.Row
con.execute(\"UPDATE agent_commands SET status='running', started_at=datetime('now') WHERE id=?\", (<command_id>,))
con.commit()
row = con.execute('SELECT j.*, ja.apply_verdict, ja.one_line_summary FROM jobs j LEFT JOIN job_assessments ja ON ja.job_id=j.id WHERE j.id=?', (<job_id>,)).fetchone()
if not row:
    print('ERROR: job not found', file=sys.stderr)
    sys.exit(1)
print(json.dumps(dict(row)))
con.close()
"
```

Capture: `apply_url` (fallback to `url`), `title`, `posted_company_name`, `description`.

---

## Step 2: Read CV content

```bash
cat /Users/zall/interviews/cv_master_content.md
```

---

## Step 3: Fetch the application page to understand the form

Navigate to the `apply_url` (or `url` if no apply_url) using web fetch or browser tools. Read the full page HTML/text.

Identify all form fields present:
- Text inputs (first name, last name, email, phone, location, LinkedIn URL, website, GitHub, years of experience, salary expectation, start date)
- Textareas (cover letter, work experience, specific questions)
- Dropdowns / selects (yes/no questions, pronouns, work authorization, relocation)
- File inputs (resume/CV upload)
- Checkboxes (diversity, consent, etc.)
- Multi-step form indicators (if multi-page, note each page)

---

## Step 4: Generate application content

Generate a JSON object with ALL content needed to fill the form. Use the CV content and job description as input.

### Fixed fields (always the same):

```json
{
  "first_name": "Aleksandr",
  "last_name": "Zalesov",
  "full_name": "Aleksandr Zalesov",
  "email": "zallesov@gmail.com",
  "phone": "",
  "location": "Malaga, Spain",
  "country": "Spain",
  "linkedin_url": "https://www.linkedin.com/in/zallesov/",
  "website_url": "https://zall.dev",
  "github_url": "",
  "resume_path": "/Users/zall/interviews/ALEKSANDR_ZALESOV-CV-05.2026.pdf",
  "years_of_experience": "18",
  "work_authorization": "No — requires work permit / visa sponsorship (EU citizen, based Spain/Germany)",
  "willing_to_relocate": "No — fully remote preferred",
  "salary_expectation": "",
  "how_did_you_hear": "Job board",
  "start_date": "Immediately / 2 weeks notice"
}
```

### Generate these fields based on the job:

**cover_letter** — Write 3–4 paragraphs. Structure:
1. Hook: why this company/role specifically (use company name, product, mission)
2. Strongest match: 2–3 achievements from CV that directly match the job requirements
3. What you bring: technical depth (AI, cloud, distributed systems) + engineering leadership
4. Close: brief, confident

Keep under 400 words. Do NOT include salutation ("Dear Hiring Manager" etc.) or closing signature — just the body paragraphs.

**screening_answers** — For any specific questions on the form (e.g., "Why do you want to work here?", "Describe your experience with X"), write a concise answer. Format as `{ "question_substring": "answer" }` where question_substring is a few words from the question to match it.

**start_date** — "Immediately" or "2–4 weeks notice" depending on form context.

Write all generated content to `/tmp/apply_fields_<job_id>.json`.

---

## Step 5: Fill the form in a headed browser

Run the filler script:

```bash
python3 /Users/zall/interviews/scripts/apply_job_filler.py \
  --apply-url "<apply_url>" \
  --fields /tmp/apply_fields_<job_id>.json \
  --job-id <job_id> \
  --report /tmp/apply_report_<job_id>.json \
  2>&1 | tee /tmp/apply_log_<job_id>.txt &
```

The script opens a **visible Chrome window**, fills all fields, uploads the CV, and then waits (keeps browser open). It does NOT click submit.

Wait up to 120 seconds for `/tmp/apply_report_<job_id>.json` to appear:

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

The report contains: `filled_fields`, `unfilled_fields`, `errors`, `screenshot_path`.

---

## Step 6: Mark command done + notify Telegram

Mark the command succeeded:

```bash
python3 -c "
import sqlite3, json
db = '<db_path>'
report = json.load(open('/tmp/apply_report_<job_id>.json'))
con = sqlite3.connect(db)
con.execute(\"UPDATE agent_commands SET status='succeeded', finished_at=datetime('now'), result_json=? WHERE id=?\",
    (json.dumps({'filled': report.get('filled_fields'), 'unfilled': report.get('unfilled_fields')}), <command_id>))
con.execute(\"UPDATE jobs SET status='applied', updated_at=datetime('now') WHERE id=? AND status != 'applied'\", (<job_id>,))
con.commit()
con.close()
"
```

Send Telegram notification:

```bash
python3 -c "
import json, urllib.request, os
from pathlib import Path

# Load env
env_file = Path.home() / '.hermes' / 'profiles' / 'interviewprep' / '.env'
token, chat_id = None, None
for line in env_file.read_text().splitlines():
    if line.startswith('TELEGRAM_BOT_TOKEN='):
        token = line.split('=',1)[1].strip()
    elif line.startswith('TELEGRAM_HOME_CHANNEL='):
        chat_id = line.split('=',1)[1].strip()

report = json.load(open('/tmp/apply_report_<job_id>.json'))
unfilled = report.get('unfilled_fields', [])
filled = report.get('filled_fields', [])
errors = report.get('errors', [])

unfilled_str = ', '.join(unfilled) if unfilled else 'none'
text = (
    f'✅ Application ready: job #{<job_id>}\n'
    f'Company: <company>\n'
    f'Role: <title>\n'
    f'Filled: {len(filled)} fields\n'
    f'Unfilled: {unfilled_str}\n'
    f'URL: <apply_url>\n'
    f'Chrome window is open — review and click Submit.\n'
)
if errors:
    text += f'Errors: {chr(10).join(errors)}\n'

payload = json.dumps({'chat_id': chat_id, 'text': text}).encode()
req = urllib.request.Request(
    f'https://api.telegram.org/bot{token}/sendMessage',
    data=payload, headers={'Content-Type': 'application/json'})
urllib.request.urlopen(req, timeout=10)
print('Telegram notified')
" 2>&1 || echo "WARN: Telegram notify failed"
```

---

## Error Handling

### If the apply URL is inaccessible or requires login:
- Try the job's main `url` instead
- If still blocked, send Telegram alert: "Could not open application form for job #N — URL blocked or requires login. Manual application needed. URL: <url>"
- Mark command failed

### If the filler script fails or times out:
- Send Telegram alert: "Apply script failed for job #N. Check /tmp/apply_log_<job_id>.txt for details."
- Mark command failed:

```bash
python3 -c "
import sqlite3
con = sqlite3.connect('<db_path>')
con.execute(\"UPDATE agent_commands SET status='failed', finished_at=datetime('now'), error=? WHERE id=?\",
    ('apply filler script failed', <command_id>))
con.commit()
con.close()
"
```

### If a required field can't be auto-detected (e.g. custom platform):
- Fill what you can
- List the unknown fields in the Telegram message so Zall can fill them manually
- Still mark command succeeded if browser is open

---

## Reminders

- The browser window must stay visible throughout — do NOT use `headless=True`
- Do NOT click any button labeled Submit, Apply, Send, or similar
- The cover letter should be personalized to the specific company and role
- Phone and salary are intentionally left blank unless the form requires them
- If the form has a "how did you hear about this job" field, answer: "Job board"
- If the form asks for gender/diversity info, do not fill (skip)
