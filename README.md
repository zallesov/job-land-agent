# JobLandAgent

An autonomous job search assistant for software engineers. Scrapes job boards, enriches listings with AI, scores them against your CV, and fills application forms in Chrome — you review and submit.

![Python](https://img.shields.io/badge/python-3.11+-blue) ![Node](https://img.shields.io/badge/node-20+-green) ![License](https://img.shields.io/badge/license-MIT-lightgrey)

---

## How it works

1. **Scrape** — Playwright pulls jobs from Greenhouse, JobLeads, Wellfound, Sprout, and Hirify into a local SQLite DB
2. **Enrich** — AI extracts salary, apply URL, full description, and remote status from each posting
3. **Sanity-check** — AI scores each job against your CV, filtering out mismatches by seniority, location, and work style
4. **Research** — Deep company analysis: funding, Glassdoor, red flags, fit score
5. **Apply** — AI fills application forms in a visible Chrome window — you review and click Submit

---

## Prerequisites

- Python 3.11+
- Node 20+
- [Hermes AI](https://hermes-agent.com) — install via their docs
- Google Chrome

---

## Setup

**1. Clone and install**

```bash
git clone https://github.com/<you>/joblandagent
cd joblandagent
pip install -r requirements.txt
cd dashboard && npm install && cd ..
```

**2. Configure**

```bash
cp config/user.yaml.example config/user.yaml
# Copy your CV as markdown:
cp ~/your-cv.md config/cv.md
```

**3. Set up Hermes profile**

```bash
# Point Hermes at the profile in this repo:
hermes --profile ./hermes-profile
# Then edit hermes-profile/config.yaml:
#   model.api_key: <your LLM provider API key>
#   (skills.external_dirs is already set to ["../skills"])
```

**4. Set up Telegram (optional but recommended)**

Follow [Hermes Telegram bot setup](https://hermes-agent.com/docs/telegram). Enables job notifications and lets you add jobs by pasting URLs in Telegram chat.

**5. Start Chrome**

```bash
bash start-chrome.sh
# Launches Chrome on localhost:9222 with a persistent profile
```

**6. Run onboarding**

```bash
hermes --profile ./hermes-profile
# Then type:
/onboarding
```

Hermes walks through the rest of setup: asking for your locations, CV, search terms, and provider accounts.

---

## Starting the dashboard

```bash
cd dashboard && npm run dev
# Opens http://localhost:3000
```

---

## Usage

| Action | How to trigger |
|---|---|
| Scrape jobs | "run scraping" in Hermes |
| Scrape specific source | "run greenhouse berlin" |
| Add job by URL | Paste any job URL in Hermes or Telegram |
| Research a job | "research job 42" |
| Apply to a job | "apply to job 42" — fills form, does NOT submit |
| Check auth sessions | "/check-auth" |
| Re-run onboarding | "/onboarding" |

---

## Supported job boards

| Board | Type | Notes |
|---|---|---|
| [Greenhouse](https://my.greenhouse.io) | Feed-based | Personalised "for you" feed |
| [JobLeads](https://jobleads.com) | Feed-based | Aggregator with salary filters |
| [Wellfound](https://wellfound.com) | UI-based | Startup-focused |
| [Sprout](https://usesprout.com) | UI-based | EU-focused |
| [Hirify](https://hirify.me) | Saved-filter UI | IT and Digital aggregator; user-managed saved filters |

---

## Configuration reference

All user config lives in `config/user.yaml` (copy from `config/user.yaml.example`):

| Key | Purpose |
|---|---|
| `user.name`, `user.email`, etc. | Identity for application forms |
| `cv_path` | Path to your CV in markdown |
| `locations` | List of `{city, country, country_code}` dicts |
| `work_style.preferred` | `remote` \| `hybrid` \| `onsite` |
| `search_terms` | Job titles to search and filter by |
| `providers` | Enable/disable each job board |
| `db_path` | SQLite DB file path |

Hirify ignores `search_terms`, `locations`, and `work_style` for search construction; create saved filters on Hirify and enable `providers.hirify`.

---

## Supported locations

Any city can be added to `config/user.yaml`. Each location needs `city`, `country`, and `country_code` (ISO 3166-1 alpha-2). Feed-based scrapers (Greenhouse, JobLeads) use the `country_code` for a country-level search. UI-based scrapers (Wellfound, Sprout) search by `city` string directly.

---

## Re-authenticating

If a job board session expires, type `"check auth"` in Hermes or run `/check-auth`. You'll be told which providers need login and shown the login URL for each.

---

## Contributing

Adding a new job board requires implementing two files:
- `scripts/providers/<name>/check_auth.py` — verify browser session
- `scripts/providers/<name>/scrape_jobs.py` — scrape and return `list[ShallowJob]`

See existing providers for the interface contract.
