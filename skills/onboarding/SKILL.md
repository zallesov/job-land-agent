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
> 1. **Scrape** job boards (Greenhouse, JobLeads, Wellfound, Sprout, Hirify) on schedule
> 2. **Enrich** each listing: extract salary, apply URL, full description
> 3. **Screen** postings against your CV — filter out mismatches, score and rank
> 4. **Research** promising companies: funding, Glassdoor, red flags, fit score
> 5. **Fill** application forms in Chrome — you review and submit
> 6. **Dashboard** at `http://localhost:3000` — browse, filter, and manage all jobs in one place
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

## Step 5.5: Ask for job preferences

After work style, ask the first open preference question:

> What are your preferences for the kind of company and role you're looking for?
>
> Answer freely — anything goes. Some things you might mention:
> - Startup vs enterprise (e.g. "only early-stage startups", "no startups, prefer stable scale-ups")
> - Industries to avoid or prefer (e.g. "no fintech, no adtech", "love climate tech")
> - IC vs management (e.g. "Individual Contributor only, no people management")
> - Company culture or values ("remote-first culture", "no on-call rotation")
> - Deal-breakers ("no equity-only comp", "no US timezone overlap required")
>
> Leave blank if you have no specific preferences.

Collect the raw text. Save as `job_preferences` in config. If blank, set to `""`.

---

## Step 5.6: Ask for languages

Ask:

> What languages do you speak, and at what level?
>
> Examples: "English (fluent), German (B2), Russian (native)", "English and Spanish only"
>
> This helps filter out roles that require a language you don't speak.

Collect the raw text. Save as `languages` in config. If blank, set to `""`.

---

## Step 5.7: Ask for desired salary

Ask:

> What is your desired salary range?
>
> Examples: "€120k–150k", "$150k+", "€100k minimum", "140–180K EUR"
>
> This will be used during screening to flag roles that are clearly underpaid.
> Leave blank if you have no hard requirement.

Collect raw text. Save as `desired_salary` in config. If blank, set to `""`.

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
> - **Hirify** (hirify.me) — saved-filter based IT and Digital aggregator

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
  hirify: false
job_preferences: "<company/role preferences or empty>"
languages: "<spoken languages or empty>"
desired_salary: "<salary range or empty>"
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

If `NOT_RUNNING`: tell user to run `bash start-chrome.sh`, wait for confirmation.

Then invoke the `check-auth` skill:

> Running auth checks for your active providers...

(Invoke check-auth skill here.)

---

## Step 9.3: Log in to research sites (mandatory)

Say:

> Now let's log in to the research sites. These sessions are **required** for company research — without them, Glassdoor, LinkedIn employee data, and Crunchbase funding info will all fail silently.
>
> I'll open each site in Chrome. Log in, then tell me "done" before I move to the next.

Open each site in sequence and wait for the user to confirm login before proceeding:

Use the visible Chrome CDP session only. Never use the non-CDP navigation tool in this agent.

### LinkedIn

```python
browser_cdp(method="Target.createTarget", params={"url": "https://www.linkedin.com/login"})
```

Say: "Log into LinkedIn, then say **done**."

Wait for "done" / "logged in" / "go".

Verify session by navigating to feed:

```python
browser_cdp(method="Target.createTarget", params={"url": "https://www.linkedin.com/feed/"})
```

Take a snapshot and confirm the feed is visible (not a login page). If still on login, ask user to try again.

### Glassdoor

```python
browser_cdp(method="Target.createTarget", params={"url": "https://www.glassdoor.com/profile/login_input.htm"})
```

Say: "Log into Glassdoor, then say **done**."

Wait for "done".

Verify by navigating to `https://www.glassdoor.com/` and confirming user is logged in (profile icon visible, not a sign-up prompt).

### Crunchbase

```python
browser_cdp(method="Target.createTarget", params={"url": "https://www.crunchbase.com/login"})
```

Say: "Log into Crunchbase, then say **done**."

Wait for "done".

Verify by navigating to `https://www.crunchbase.com/` and checking the user avatar is present.

### Summary

After all three:

```
Research site sessions:
  LinkedIn    ✅ logged in
  Glassdoor   ✅ logged in
  Crunchbase  ✅ logged in
```

For any that failed: show the login URL again and prompt the user to retry. Do not proceed to Step 9.5 until all three are confirmed — these sessions are mandatory for company research.

---

## Step 9.5: Explain Chrome profile separation

After auth checks pass, optionally mention:

> One note: this setup uses a **dedicated** Chrome profile at `.chrome-profile/` inside the project directory, separate from your everyday Chrome. Sessions (logins, cookies) you enter here persist between restarts in **this profile only** — they don't carry over from your main Chrome. If you log into Greenhouse/Wellfound/JobLeads once, those sessions will survive restarts.

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
> | View dashboard | "open dashboard" or `/run-dashboard` |
> | Re-check auth | "/check-auth" |
>
> Type **"run scraping"** to kick off your first pipeline run!
