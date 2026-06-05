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

## User install

Install this repo as a Hermes profile distribution:

```bash
hermes profile install github.com/zallesov/job-land-agent --alias
```

Set the required model key in your shell environment:

```bash
export DEEPSEEK_API_KEY="<your DeepSeek API key>"
```

Then install app dependencies inside the installed profile directory:

```bash
cd ~/.hermes/profiles/joblandagent
pip install -r requirements.txt
pnpm install
```

Copy the sample user config and add your CV:

```bash
cp config/user.yaml.example config/user.yaml
cp ~/your-cv.md config/cv.md
```

Runtime state, local config, auth, logs, browser profiles, and databases live under `~/.hermes/profiles/joblandagent/` and are not committed to this repo.

The installed profile is self-contained. Hermes is configured with `terminal.cwd: .`, so commands run from the active profile root. Do not start the dashboard from a developer checkout when testing the installed profile.

## Local development

**1. Clone and install a local profile**

```bash
git clone https://github.com/zallesov/job-land-agent
cd joblandagent
tmpdir=$(mktemp -d)
for p in distribution.yaml SOUL.md config.yaml .env.EXAMPLE README.md package.json pnpm-lock.yaml pnpm-workspace.yaml requirements.txt start-chrome.sh config skills scripts dashboard; do
  if [ -d "$p" ]; then
    rsync -a --exclude node_modules --exclude .next "$p/" "$tmpdir/$p/"
  else
    cp "$p" "$tmpdir/$p"
  fi
done
hermes profile install "$tmpdir" --name joblandagent-dev --alias --force --yes
cd ~/.hermes/profiles/joblandagent-dev
pip install -r requirements.txt
pnpm install
```

Developer directive: after any change to distributable files, sync the installed Hermes dev profile before testing in Hermes. Distributable files include `SOUL.md`, `config.yaml`, `distribution.yaml`, `.env.EXAMPLE`, `README.md`, `package.json`, `pnpm-lock.yaml`, `pnpm-workspace.yaml`, `requirements.txt`, `start-chrome.sh`, `config/`, `skills/`, `scripts/`, and `dashboard/`.

```bash
tmpdir=$(mktemp -d)
for p in distribution.yaml SOUL.md config.yaml .env.EXAMPLE README.md package.json pnpm-lock.yaml pnpm-workspace.yaml requirements.txt start-chrome.sh config skills scripts dashboard; do
  if [ -d "$p" ]; then
    rsync -a --exclude node_modules --exclude .next "$p/" "$tmpdir/$p/"
  else
    cp "$p" "$tmpdir/$p"
  fi
done
hermes profile install "$tmpdir" --name joblandagent-dev --alias --force --yes
```

Then install/update runtime dependencies from the profile root if needed:

```bash
cd ~/.hermes/profiles/joblandagent-dev
pip install -r requirements.txt
pnpm install
```

This repo root is the distribution source. Runtime profile state belongs under `~/.hermes/profiles/<profile-name>/`, not inside the repo. Keep `joblandagent` and `joblandagent-dev` independent by running Hermes and dashboard commands from the profile being tested:

```bash
hermes -p joblandagent      # installed distribution profile
hermes -p joblandagent-dev  # local development distribution profile
```

Each profile owns its own `jobs.db`, `config/user.yaml`, `config/cv.md`, logs, sessions, and dashboard dependencies.

**2. Configure**

```bash
cp config/user.yaml.example config/user.yaml
# Copy your CV as markdown:
cp ~/your-cv.md config/cv.md
```

**3. Configure model key**

```bash
export DEEPSEEK_API_KEY="<your DeepSeek API key>"
```

Do not commit API keys, `.env`, `jobs.db`, local CV files, or runtime profile state.

**4. Set up Telegram (optional but recommended)**

Follow [Hermes Telegram bot setup](https://hermes-agent.com/docs/telegram). Enables job notifications and lets you add jobs by pasting URLs in Telegram chat.

**5. Start Chrome**

```bash
bash start-chrome.sh
# Launches Chrome on localhost:9222 with a persistent profile
```

**6. Run onboarding**

```bash
hermes -p joblandagent-dev
# Then type:
/onboarding
```

Hermes walks through the rest of setup: asking for your locations, CV, search terms, and provider accounts.

## Starting the dashboard

Start the dashboard from the active profile root. This is what makes `../jobs.db` resolve to that profile's local database:

```bash
pnpm run dev
# Opens http://localhost:3000
```

For manual testing outside Hermes, use an absolute profile path:

```bash
cd ~/.hermes/profiles/joblandagent
pnpm run dev
```

For development-profile testing:

```bash
cd ~/.hermes/profiles/joblandagent-dev
pnpm run dev
```

To test on another port:

```bash
PORT=3717 pnpm run dev
```

---

## Usage

| Action | How to trigger |
|---|---|
| Scrape jobs | "run scraping" in Hermes |
| Scrape specific source | "run greenhouse berlin" |
| Import spreadsheet jobs | `/job-pipeline/import-from-spreadsheet` |
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
| CSV feed | Import-only | Temporary spreadsheet import via `tmp/filtered_dev.csv`; not enabled in the default provider set |

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
