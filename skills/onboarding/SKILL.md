---
name: onboarding
description: First-time setup wizard for JobLandAgent. Asks for CV, user identity, locations, work style, search terms, and provider accounts. Writes config/user.yaml. Runs check-auth at the end. Triggered by "/onboarding", "set up joblandagent", or "I'm new here".
---

# Onboarding

## Trigger

`/onboarding`, "set up", "set up joblandagent", "I'm new here", "help me get started"

## Execution Rules

- Ask questions one at a time. Wait for each answer before proceeding.
- Write all collected values to `config/user.yaml` at the end (Step 8), not incrementally.
- Be conversational and encouraging. This is a guided wizard, not a form.

---

## Step 1: Welcome

Say:

> Welcome to **JobLandAgent**! 👋
>
> I'm your autonomous job search assistant. Here's what I do:
> 1. **Scrape** job boards (Greenhouse, JobLeads, Wellfound, Sprout) on schedule
> 2. **Enrich** each listing: extract salary, apply URL, full description
> 3. **Sanity-check** postings against your CV — filter out mismatches
> 4. **Research** promising companies: funding, Glassdoor, red flags, fit score
> 5. **Fill** application forms in Chrome — you review and submit
>
> Let's get you set up. I'll ask a few questions and write your config file.

---

## Step 2: Ask for CV path

Ask:

> Where is your CV in markdown format? (e.g. `~/cv.md` or `/Users/you/docs/cv.md`)
> If you don't have one yet, I can help you create it from a PDF or paste.

Accept the path. Verify the file exists:

```bash
test -f "<cv_path>" && echo "EXISTS" || echo "NOT_FOUND"
```

If `NOT_FOUND`: tell user to create/copy it first, then come back. If `EXISTS`: copy to `config/cv.md`:

```bash
cp "<cv_path>" config/cv.md
```

---

## Step 3: Ask for user identity

Ask:

> What's your full name?

Then:

> Your email address?

Then:

> Your LinkedIn profile URL? (e.g. `https://linkedin.com/in/yourhandle`)

Then:

> Path to your resume PDF? (used for form uploads, e.g. `~/resume.pdf`)

Accept each answer. Verify the PDF exists:

```bash
test -f "<resume_pdf_path>" && echo "EXISTS" || echo "NOT_FOUND"
```

Copy PDF to `config/resume.pdf` if path differs from `config/resume.pdf`.

---

## Step 4: Ask for target locations

Ask:

> Which cities or regions are you targeting for jobs? (You can list multiple, e.g. "Berlin, Barcelona, London")
>
> For each location I'll need:
> - City name
> - Country name
> - Country code (ISO 3166-1 alpha-2, e.g. DE, ES, GB)

Collect all locations. Format as a list of dicts.

---

## Step 5: Ask for work style

Ask:

> What's your work style preference?
> - **Remote** — fully remote only
> - **Hybrid** — flexible (some days in office)
> - **Onsite** — full-time in office

Then:

> Are you willing to relocate? (yes/no)

Map answer to `preferred: remote | hybrid | onsite` and `willing_to_relocate: true | false`.

---

## Step 6: Infer and confirm search terms

Read the CV content:

```bash
cat config/cv.md
```

Using the CV content, infer 4–6 relevant job titles the user should search for. Show the list:

> Based on your CV, I suggest searching for these job titles:
> - Software Engineer
> - AI Engineer
> - Engineering Manager
> - Platform Engineer
>
> Edit this list if needed. Add or remove titles.

Wait for confirmation or edits.

---

## Step 7: Ask about job board accounts

Ask:

> Which job boards have you signed up for? (I'll only scrape boards where you have an account)
>
> - **Greenhouse** (my.greenhouse.io) — personalized "for you" feed
> - **JobLeads** (jobleads.com) — aggregator with salary filters
> - **Wellfound** (wellfound.com) — startup-focused
> - **Sprout** (usesprout.com) — EU-focused

If a user hasn't signed up for a board, show the signup URL and suggest they sign up.

Set `providers.<name>: true` for each confirmed board.

---

## Step 8: Write config/user.yaml

Write the collected values to `config/user.yaml` using `write_file` (avoids pyyaml dependency issues):

```yaml
user:
  name: <name>
  email: <email>
  linkedin_url: <linkedin_url>
  resume_pdf_path: config/resume.pdf
cv_path: config/cv.md
locations:
  - city: <city>
    country: <country>
    country_code: <code>
work_style:
  preferred: <remote|hybrid|onsite>
  willing_to_relocate: false
search_terms:
  - Title One
  - Title Two
providers:
  greenhouse: false
  jobleads: false
  wellfound: false
  sprout: false
db_path: jobs.db
```

---

## Step 9: Verify Chrome and auth

Say:

> Now let's verify your browser sessions. Chrome must be running first.

Check Chrome:

```bash
curl -s http://localhost:9222/json/version 2>&1 | head -1 | grep -q "{" && echo "OK" || echo "NOT_RUNNING"
```

If `NOT_RUNNING`: tell user to run `~/start-chrome.sh`, wait for confirmation.

Then invoke the `check-auth` skill:

> Running auth checks for your active providers...

(Invoke check-auth skill here.)

---

## Step 10: Explain the system and close

Say:

> 🎉 Setup complete! Here's how to use JobLandAgent:
>
> | What | How |
> |---|---|
> | Scrape jobs | "run scraping" |
> | Add a specific job | Paste any job URL in this chat |
> | Research a job | "research job 42" |
> | Apply to a job | "apply to job 42" |
> | View dashboard | http://localhost:3000 (run `cd dashboard && npm run dev`) |
> | Re-check auth | "/check-auth" |
>
> Type **"run scraping"** to kick off your first pipeline run!
