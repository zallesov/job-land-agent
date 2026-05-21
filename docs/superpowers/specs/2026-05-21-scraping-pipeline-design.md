# Scraping Pipeline — Design Spec
**Date:** 2026-05-21
**Status:** Approved

---

## Context

The current scraping setup fuses list-scraping and per-job enrichment into single provider scripts,
uses the YAML workflow file as a natural-language Hermes prompt (not a machine-executable spec),
has no dedup key, no auth wait loop, and no sanity check before research.

This spec defines a restructured pipeline that is deterministic, provider-configurable, testable
per-phase and per-provider, and cleanly separates scripted steps from LLM steps.

---

## Pipeline Flow

```
check_auth → scrape_jobs → dedup → ingest → enrich → sanity_check → telegram
```

Each step is an importable Python function. `scraping_pipeline.py` imports and calls them directly.
No subprocess chaining between steps — subprocess is only used inside `hermes_call()` to invoke Hermes.

```python
# scraping_pipeline.py --provider greenhouse --location berlin

from providers.greenhouse.check_auth import check_auth
from providers.greenhouse.scrape_jobs import scrape_jobs
from pipeline.dedup           import dedup_jobs
from pipeline.ingest          import ingest_jobs
from pipeline.enrich_job      import enrich_job
from pipeline.sanity_check_job import sanity_check_job
from pipeline.notify          import send_daily_digest
import db                                     # scripts/db.py — get_job(), get_connection()

def run(provider, location, cdp_url):
    check_auth(cdp_url)                       # AuthError → hard stop
    raw_jobs  = scrape_jobs(location, cdp_url)
    new_jobs  = dedup_jobs(raw_jobs)          # filters by dedup_key vs DB
    job_ids   = ingest_jobs(new_jobs)         # inserts status=listed

    enrich_failures = []
    for job_id in job_ids:
        result = enrich_job(job_id)
        if not result.success:
            enrich_failures.append((job_id, result.error))

    # Only run sanity check on successfully enriched jobs
    enriched_ids = [jid for jid in job_ids if db.get_job(jid)["status"] == "new"]
    sanity_failures = []
    for job_id in enriched_ids:
        result = sanity_check_job(job_id)
        if not result.success:
            sanity_failures.append((job_id, result.error))

    send_daily_digest(enrich_failures=enrich_failures, sanity_failures=sanity_failures)
```

---

## Folder Structure

```
scripts/
  scraping_pipeline.py              # orchestrator

  providers/
    _shared/
      auth_check.py                 # wait_for_auth() — shared by all check_auth modules
      job_filter.py                 # is_relevant()   — shared by all scrape_jobs modules
    greenhouse/
      check_auth.py
      scrape_jobs.py
    jobleads/
      check_auth.py
      scrape_jobs.py
    wellfound/
      check_auth.py
      scrape_jobs.py
    sprout/
      check_auth.py
      scrape_jobs.py

  pipeline/
    types.py                        # ShallowJob, HermesResult
    dedup.py
    ingest.py
    enrich_job.py
    sanity_check_job.py
    notify.py
    hermes.py                       # hermes_call() — single Hermes CLI wrapper

  db.py                             # existing, unchanged
  research_job.py                   # standalone, web-triggered, NOT part of pipeline

  skills/
    enrich-job/SKILL.md
    sanity-check-job/SKILL.md

tests/
  fixtures/
    greenhouse/
      search_results.html
      job_page.html
      scrape_output.json
    jobleads/  ...
    wellfound/ ...
    sprout/    ...
    hermes/
      enrich_success.json
      enrich_failure.json
      enrich_timeout.json
      sanity_pass.json
      sanity_skip.json
      sanity_failure.json
  providers/
    greenhouse/
      test_check_auth.py
      test_scrape_jobs.py
    jobleads/
      test_check_auth.py
      test_scrape_jobs.py
    wellfound/
      test_check_auth.py
      test_scrape_jobs.py
    sprout/
      test_check_auth.py
      test_scrape_jobs.py
  pipeline/
    test_dedup.py
    test_ingest.py
    test_enrich_job.py
    test_sanity_check_job.py
    test_notify.py
    test_hermes.py
  test_scraping_pipeline.py
  test_research_job.py
  e2e/
    test_greenhouse_live.py         # @pytest.mark.e2e — manual only, real Chrome + Hermes
```

---

## Data Types (`pipeline/types.py`)

```python
@dataclass
class ShallowJob:
    provider: str
    title: str
    company: str
    url: str
    location: str
    country: str | None   # always populated by supported providers; None only if provider omits it
    dedup_key: str        # "{company}::{title}"
    posting_date: str | None
    salary_raw: str | None

@dataclass
class HermesResult:
    success: bool
    data: dict            # parsed JSON from skill stdout
    error: str | None     # failure reason (timeout / stderr / parse error / skill error)
    raw_output: str       # full Hermes stdout for debugging
```

`dedup_key` is computed in `scrape_jobs()` before any DB interaction.

---

## Function Interfaces

```python
# providers/{provider}/check_auth.py
def check_auth(cdp_url: str) -> None
# Navigates to provider auth-check URL via CDP.
# If session valid: returns immediately.
# If auth required: sends Telegram alert, polls every 15s up to 10 min.
# Raises AuthError on timeout.

# providers/{provider}/scrape_jobs.py
def scrape_jobs(location: str, cdp_url: str) -> list[ShallowJob]
# Playwright list-only scrape. No per-job page visits.
# Provider-specific DOM extraction. Calls is_relevant() to pre-filter.

# pipeline/dedup.py
def dedup_jobs(jobs: list[ShallowJob]) -> list[ShallowJob]
# Queries DB for existing dedup_keys. Returns only jobs not already present.

# pipeline/ingest.py
def ingest_jobs(jobs: list[ShallowJob]) -> list[int]
# Inserts new jobs with status=listed. Returns list of new job IDs.

# pipeline/enrich_job.py
def enrich_job(job_id: int) -> HermesResult
# Reads job from DB. Calls hermes_call("enrich-job", {job_id, url, cv_path}).
# On success: writes description/apply_url/salary/date_posted to DB, status=new.
# On failure: status=enrich_failed, comment=error.

# pipeline/sanity_check_job.py
def sanity_check_job(job_id: int) -> HermesResult
# Reads job from DB. Calls hermes_call("sanity-check-job", {job_id, cv_path}).
# verdict=pass:    status stays new (ready for research)
# verdict=skip:    status=not_interested, comment=reason
# On failure:      status=sanity_failed, comment=error

# pipeline/hermes.py
def hermes_call(skill: str, context: dict, timeout_sec: int = 300) -> HermesResult
# Builds prompt + calls: hermes --profile interviewprep --skill {skill} --output-format json
# Handles: timeout, non-zero exit, unparseable output → HermesResult(success=False)

# pipeline/notify.py  ← new thin wrapper over existing telegram_notify.py
# telegram_notify.py is kept unchanged (used by web UI, research_job.py, legacy pipeline)
def send_daily_digest(enrich_failures=None, sanity_failures=None) -> None

# scripts/research_job.py  (standalone, not part of pipeline)
def research_job(job_id: int) -> HermesResult
# Called from web interface. Uses existing research skill.
```

---

## Hermes Integration (`pipeline/hermes.py`)

All Hermes communication is isolated in `hermes_call()`. Neither `enrich_job` nor `sanity_check_job`
call the Hermes CLI directly. Hermes outputs structured JSON to stdout; Python owns all DB writes.

**`cv_path` resolution:** Both `enrich_job` and `sanity_check_job` pass the CV to Hermes.
Resolved as: `CV_PATH = PROJECT_ROOT / "cv_master_content.md"` (defined in `pipeline/hermes.py`).

**`build_prompt()` contract:**
```python
def build_prompt(skill: str, context: dict) -> str:
    # enrich-job  → "Enrich job 42. URL: https://... . CV: /path/cv.md"
    # sanity-check-job → "Sanity check job 42. CV: /path/cv.md"
    parts = [f"Run skill {skill}."]
    for k, v in context.items():
        parts.append(f"{k}: {v}")
    return " ".join(parts)
```

```python
def hermes_call(skill: str, context: dict, timeout_sec: int = 300) -> HermesResult:
    prompt = build_prompt(skill, context)
    cmd = [
        "hermes", "--profile", "interviewprep",
        prompt,
        "--skill", skill,
        "--workdir", PROJECT_ROOT,
        "--output-format", "json",
        "--no-interactive",
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_sec)
    except subprocess.TimeoutExpired:
        return HermesResult(success=False, data={}, error="timeout", raw_output="")

    if proc.returncode != 0:
        return HermesResult(success=False, data={}, error=proc.stderr.strip(), raw_output=proc.stdout)

    try:
        # extract_json_block: finds first { ... } block in mixed stdout
        # defined in pipeline/hermes.py as:
        #   s = proc.stdout; return s[s.index("{"):s.rindex("}")+1]
        data = json.loads(extract_json_block(proc.stdout))
        success = data.get("status") == "success"
        return HermesResult(success=success, data=data, error=data.get("error"), raw_output=proc.stdout)
    except Exception as e:
        return HermesResult(success=False, data={}, error=f"parse error: {e}", raw_output=proc.stdout)
```

**Hermes CLI flags:** exact flags (`--output-format`, `--no-interactive`) to be verified against
actual Hermes CLI before implementation. Wrapper is designed for easy adjustment.

### Skill Output Contract

Skills define their own output schema in SKILL.md. `hermes_call()` parses whatever JSON block
appears in stdout. Failure cases are defined in the skill, not inferred by the wrapper.

```json
// enrich-job success
{ "status": "success", "title": "...", "description": "...",
  "apply_url": "...", "salary_range": "90-120K EUR", "date_posted": "2026-05-10" }

// enrich-job failure
{ "status": "failure", "error": "login wall / page not found / extraction failed" }

// sanity-check-job pass
{ "status": "success", "verdict": "pass", "reason": "Remote senior backend, matches profile" }

// sanity-check-job skip  ← status="success"; HermesResult.success=True
{ "status": "success", "verdict": "skip", "reason": "On-site only, Berlin office required" }
// sanity_check_job() detects skip via result.data["verdict"] == "skip", NOT via result.success==False

// sanity-check-job failure
{ "status": "failure", "error": "could not load job description" }
```

---

## DB Status Transitions

```
(new job arrives)
      ↓
   listed         ← after ingest_jobs()
      ↓
   new            ← after enrich_job() success
   enrich_failed  ← after enrich_job() Hermes error

   new            ← after sanity_check_job() verdict=pass  (no change)
   not_interested ← after sanity_check_job() verdict=skip
   sanity_failed  ← after sanity_check_job() Hermes error
```

**Dashboard compatibility:** `listed`, `enrich_failed`, `sanity_failed` are new status values.
Before implementing, add them to `dashboard/app/components/JobList.tsx`:
- `STATUS_COLORS` map
- `STATUS_PRIORITY` sort order:
  - `listed: 5.5` (between `new:5` and `researching:6`)
  - `enrich_failed: 10` (below `archived:9`)
  - `sanity_failed: 11`

**DB schema additions** (`scripts/db.py` — add to existing migration block):
```sql
ALTER TABLE jobs ADD COLUMN dedup_key TEXT;
CREATE UNIQUE INDEX IF NOT EXISTS idx_jobs_dedup_key ON jobs(dedup_key);
```
The unique index enforces dedup at DB level and makes `dedup_jobs()` queries efficient.

---

## Error Handling Policy

| Step | Failure | Policy |
|---|---|---|
| `check_auth` | AuthError / timeout | Hard stop, Telegram alert |
| `scrape_jobs` | Exception / empty | Hard stop; orchestrator catches exception, calls `telegram_notify.pipeline_failure(provider, error)` |
| `dedup_jobs` | DB error | Hard stop |
| `ingest_jobs` | DB error | Hard stop |
| `enrich_job` | Any Hermes failure | Per-job skip, `enrich_failed`, continues loop |
| `sanity_check_job` | Any Hermes failure | Per-job skip, `sanity_failed`, continues loop |
| `send_daily_digest` | Always runs | Best-effort, includes failure summary |

**Re-run safety:** All steps are idempotent. Dedup prevents double-ingest. `enrich_job` and
`sanity_check_job` can be re-run on failed jobs independently.

---

## Testing Strategy

**Three levels:**

| Level | External deps | When |
|---|---|---|
| Unit | All mocked | CI on every commit |
| Integration | Real SQLite in-memory, mock CDP + Hermes | CI on every commit |
| E2E (`@pytest.mark.e2e`) | Real Chrome + real Hermes | Manual only |

**Per-file test coverage:**

| Test file | Mocks | Verifies |
|---|---|---|
| `providers/*/test_check_auth.py` | CDP page URL | Auth detected, wait loop, timeout→AuthError |
| `providers/*/test_scrape_jobs.py` | CDP page HTML (fixture) | Fields extracted, is_relevant() filtering |
| `pipeline/test_dedup.py` | DB | Existing dedup_key skipped, new passes |
| `pipeline/test_ingest.py` | DB | Fields written, status=listed |
| `pipeline/test_hermes.py` | subprocess | Timeout, bad exit, unparseable JSON, success |
| `pipeline/test_enrich_job.py` | hermes_call + DB | DB write on success; enrich_failed on all failure modes |
| `pipeline/test_sanity_check_job.py` | hermes_call + DB | pass→new, skip→not_interested, failure→sanity_failed |
| `pipeline/test_notify.py` | telegram | Digest includes failure counts |
| `test_scraping_pipeline.py` | All above | Orchestration, hard-stop vs soft-fail, partial enrich |
| `test_research_job.py` | hermes_call + DB | Standalone call, correct context passed to Hermes |

Fixtures in `tests/fixtures/` provide canned HTML (per provider) and canned HermesResult JSON
(per skill × outcome) so tests never depend on live services.

---

## Out of Scope

- `research_job.py` — standalone, triggered from web UI, uses existing research skill
- Sanity check kanban ticket creation — future work
- LinkedIn provider — future work
- `scraping-workflow.yaml` — superseded by `scraping_pipeline.py`; kept as reference doc only
- `config/pipeline_config.json` — superseded by `scraping_pipeline.py --provider` flag; kept for reference only. The `skill` keys in that file (`"greenhouse-scraper"` etc.) no longer drive execution.
