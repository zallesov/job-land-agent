# WellFound Pipeline — Resumable, DB-Driven Workflow

**Status:** PLANNED (not yet started)
**Owner:** Zall
**Date:** 2026-06-25
**Provider scope:** `wellfound` (the design generalises to other providers later, but this plan ships WellFound only)

---

## 1. What we want

One end-to-end WellFound job pipeline that is **resumable, restartable, and human-gated**:

- Runs the steps: launch browser → check session → scrape → ingest → enrich → screen.
- **Every step reads its input from the database and writes its result back to the database, incrementally, one record at a time.**
- If the run dies (crash, bot-detection, machine off) at any point, **re-running it picks up exactly where it stopped** — no repeated work (no re-enrichment of already-enriched jobs, no re-screening of already-screened jobs).
- On **any** unclear / unexpected situation (lost session, bot-check, missing MCP tool, a step exiting non-zero) the orchestrator **stops and waits for a human** instead of guessing.
- The orchestrator does **nothing except these steps**. Each step is a deterministic script, a skill, or a script+skill combo. Each step is covered by tests.

The end product is a workflow we can hand to Hermes to run as a daemon, but which we first **validate ourselves** by having a Sonnet subagent play the role of the orchestrator and run the whole thing through MCP (see Phase 5).

## 2. Why we are doing this

The current WellFound flow already exists (`wellfound-flow` + 7 sub-skills) but its resumability is built on **local file checkpoints** (`enriched.jsonl`, `shortlist_new.json`, …). That has real problems:

- **Fragile across restarts.** Wipe `tmp/` (or run on a fresh machine / container) and the pipeline loses its place. State that matters lives in throwaway files instead of the database.
- **Two competing state fields.** Records carry both `status` and `pipeline_status`, written inconsistently. There is no single source of truth for "where is this job in the pipeline".
- **Writes are deferred.** Enrichment writes to a file; a *separate* manual agent step later pushes to the DB. So partial progress is not durable — a crash between "enriched to file" and "written to DB" loses work.
- **Screen is broken.** `screen_job.py` is parked on the now-removed `pb_client` and writes to a `job_assessments` collection MCP does not expose. Step 10 cannot run.

The fix is to make **the database the workflow engine**: the `status` field is a state machine, every step is a pure function `(jobs WHERE status = X) → (jobs WHERE status = Y)`, and the database — not local files — is what makes the pipeline resumable. This was previously impossible from scripts (no Python path to the DB); it is now possible because `agent/scripts/mcp_client.py` is a sanctioned MCP client. Local files become pure scratch.

## 3. Architecture — three layers

```
LAYER 1: state machine = jobs.status in the DB     ← this IS the "workflow engine"
LAYER 2: each step = deterministic script/skill (read DB by status → act → write DB by status)
LAYER 3: orchestrator skill = dumb sequencer + the single human-escalation point
```

- **Hermes has no DAG/workflow engine** (confirmed from its docs — only cron `--script`, webhook routes, and skills). So we do not express the pipeline as a Hermes "workflow". The database state machine does that job, and a thin orchestrator skill sequences the steps.
- **All JobLand DB access is MCP-only** (policy in `agent/CLAUDE.md`). Scripts reach the DB exclusively through `scripts/mcp_client.py`. No direct PocketBase clients, no SQL.
- **Browser/scrape/enrich page-reading is local work** (external provider data) and may use Playwright / agent-browser. Only the *writes to JobLand* go through MCP.

## 4. State machine (final)

Single field: **`status`**. `pipeline_status` is removed everywhere. Scoped to `provider = "wellfound"`:

```
(scraped → local file)
        │  ingest (step 6)
        ▼
       new ───────► enriched ───────► screened
        ▲  enrich      ▲   screen
        │  (step 8)    │   (step 10)
        │              │
   on failure the status does NOT advance.
   The next run re-selects that status and retries it.
```

- **No in-progress / claim statuses** (`enriching`, `screening`). A job is `new`, `enriched`, or `screened` — nothing in between. Within a single run the worklist is fetched once and split across ≤5 workers, so two workers never grab the same job. Cross-run concurrency is not a concern (single daemon instance).
- **Failure handling = do nothing.** If enrichment fails for a job, it stays `new` and the next run retries it. If screening fails, the job stays `enriched` and the next run re-screens it. Resumability is automatic because the terminal status is only written on success.
- **Idempotency = "skip if already advanced".** Each step only selects jobs in its *input* status, so already-advanced jobs are never reprocessed (no re-enrichment, no re-screening).

> **Poison-pill risk (accepted for MVP):** a job that fails its step every time stays in its input status forever and is retried every run. We accept this for now; the bot-detection halt (which stops the whole run for a human) covers the common cause. Revisit with an attempt counter / `*_failed` status if it becomes a problem.

## 5. The 10 functional steps → assets

| # | Step | Asset | Notes |
|---|------|-------|-------|
| 1 | Launch Chrome | `start-chrome.sh`, `wellfound-preflight` | headed/Xvfb, CDP on 9222 |
| 2 | Check WellFound session; **none → STOP** | `wellfound-check-auth` | read-only |
| 3 | Scrape + scroll to bottom → local file | `wellfound-parse-jobs`, `wellfound_scrape.sh` | local only, no DB writes |
| 4 | Pull all `wellfound` jobs from MCP | `jobs_list {origin:"wellfound"}` | uses the new origin filter |
| 5 | First dedup by `dedup_key` (2 files in → 1 out) | `dedup_jobs.py` | already takes `input` + `--existing` → `--out` |
| 6 | Insert new records via MCP, `status=new` | `pipeline/ingest.py` | one status field only |
| 7 | Pull `wellfound` + `status=new` from MCP | `jobs_list {origin:"wellfound", status:"new"}` | new origin+status filter |
| 8 | Enrich in parallel (≤5), **write each result to DB immediately** (`status=enriched`); bot-detection → pause for human | `wellfound_enrich.py` | now writes to DB per-job via mcp_client; keeps bot-halt exit 2 |
| 9 | Pull `wellfound` + `status=enriched` from MCP | `jobs_list {origin:"wellfound", status:"enriched"}` | new origin+status filter |
| 10 | Screen in parallel (≤5), write verdict + `status=screened` to the job, one by one | **new `screen-job` skill** (subagent, cheap model) | verdict lives on the job record (A1) |

## 6. Decisions (locked)

- **A1 — screen verdict lives on the job record** (1:1). The `job_assessments` collection is dropped. This requires adding verdict columns to the PocketBase `jobs` collection (see T1 — they are currently MISSING in prod).
- **No ING/claim statuses.** States are `new → enriched → screened` only.
- **Single `status` field.** `pipeline_status` removed from all scripts and skills.
- **`screen-job` is a skill, not a Python script.** It runs on a subagent with a cheap model, reaches into MCP itself (`jobs_get` by id → screen → `jobs_update`), and writes the verdict + `status=screened` back onto the job.
- **MCP-only writes**, via `scripts/mcp_client.py`.

### T4 normalisation rule (decided)
Normalising the 92 existing dirty WellFound rows (`status=''`): **when in doubt → `new`.** All `provider=wellfound && status=''` rows are set to `new`. The 16 already `enriched` stay `enriched`. Re-enriching a `new` row is safe (idempotent + dedup-guarded); the only cost is an extra enrich pass, which is acceptable.

---

## 7. Phases, tasks, and per-task verification

Critical path: **T1 → (Phase 1 + Phase 2 in parallel) → T8 → Phase 4 → Phase 5.**

### Phase 0 — Blocker (do first, alone)

**T1 — Add screen columns to the PocketBase `jobs` collection (prod).**
- *What:* add `apply_verdict` (text), `relevance_score` (number), `one_line_summary` (text), `screen_summary` (text), plus any remaining verdict fields we keep (`seniority_fit`, `tech_stack_fit`, `remote_eligibility`, `salary_assessment`).
- *Why:* A1 stores the verdict on the job; MCP `jobs_update` accepts arbitrary fields but PocketBase rejects unknown columns, so the columns must exist first. They are MISSING in prod today.
- *Files / surface:* prod PocketBase schema (`pb.zall.dev`), via PB admin API.
- *Verify:* `jobs_update` on a throwaway job with all new fields → HTTP 200; read the record back via MCP and confirm every field round-trips. Confirm no existing field was altered.

### Phase 1 — Cleanup (3 tasks, parallel, independent)

**T2 — Purge `pipeline_status` everywhere.**
- *What:* remove every read/write of `pipeline_status` from scripts and skills; `status` is the only state field.
- *Why:* two competing state fields = no single source of truth.
- *Files:* `pipeline/ingest.py`, `mcp_client.py` (`update_job_status` sets both today), `wellfound-*` skills, any other references.
- *Verify:* `grep -rn pipeline_status agent/scripts agent/skills` returns 0 hits; existing test suite stays green.

**T3 — `ingest.py` writes `status=new`, single field.**
- *What:* ingest sets `status="new"` for non-skip jobs and writes no `pipeline_status`.
- *Why:* step 6 of the spec; aligns ingest with the state machine.
- *Files:* `pipeline/ingest.py`.
- *Verify:* unit test with `FakeMCPClient` — an ingested non-skip job has `status == "new"` and no `pipeline_status` key; a `skip` job is not returned in the id list.

**T4 — Normalise the 92 dirty WellFound rows.**
- *What:* one-off script to set `status="new"` on all existing `provider=wellfound` rows that currently have `status=''` (when in doubt → `new`, per §6). Rows already `enriched`/`screened` are left untouched.
- *Why:* the state machine assumes every WellFound job is in a known status; empty status is unhandled.
- *Files:* one-off script under `scripts/` (or a documented MCP call sequence).
- *Verify:* count of `provider=wellfound && status=''` is 0 afterwards; spot-check 3 rows match the rule; total WellFound count unchanged (no rows lost/created).

### Phase 2 — Step scripts (depend on Phase 1)

**T5 — Enrich writes to the DB per job.**
- *What:* `wellfound_enrich.py` selects its worklist by DB status (input = `new`), enriches ≤5 concurrent, and **immediately `jobs_update`s each finished job to `status=enriched`** with the enriched fields via `mcp_client`. Remove the separate "agent writes later" step. Keep the bot-detection halt (exit code 2, browser brought on-screen, blocked job NOT advanced).
- *Why:* durable incremental progress; resumability comes from DB status, not the local checkpoint file.
- *Files:* `scripts/wellfound_enrich.py`; `wellfound-enrich-jobs` skill text updated to match (no more "write step is a separate agent action").
- *Verify:* unit tests with a fake browser extraction + `FakeMCPClient`:
  1. each job ends at `status=enriched` with the expected fields written;
  2. a job already `enriched` is skipped (not re-enriched);
  3. bot-detection halt → process exits 2 and the blocked job is **not** advanced/written.

**T6 — Fetch-by-status helper (steps 4 / 7 / 9).**
- *What:* small `wellfound_fetch.py` that calls `jobs_list {origin:"wellfound", status:<S>}` (the filter shipped earlier today) and dumps to a local file for the next step's input.
- *Why:* steps 4/7/9 need the current DB worklist as a file; one tested helper covers all three.
- *Files:* new `scripts/wellfound_fetch.py`.
- *Verify:* unit test with `FakeMCPClient` seeded with mixed providers/statuses → helper returns only `provider=wellfound` rows in the requested status.

**T7 — Dedup confirm + test (step 5).**
- *What:* confirm `dedup_jobs.py` matches the spec (2 input files → deduped output by `dedup_key`); add a test if missing.
- *Why:* step 5 is "first dedup by dedup_key"; it is mostly done but needs a regression test.
- *Files:* `scripts/dedup_jobs.py`, `tests/`.
- *Verify:* unit test on fixtures — a scraped job whose `dedup_key` is in the existing set is dropped; a genuinely new one survives; in-batch duplicates collapse.

### Phase 3 — Screen (depends on T1)

**T8 — New `screen-job` skill (subagent, cheap model).**
- *What:* create `skills/screen-job/` (provider-agnostic). The skill: takes a job id (or selects `provider=wellfound && status=enriched`), pulls the job via MCP `jobs_get`, runs the screening prompt against the CV, and writes the verdict fields + `status=screened` back onto the job via `jobs_update`. Runs on a subagent with a cheap model. Delete the parked `scripts/pipeline/screen_job.py` and its quarantined test.
- *Why:* step 10; unblocks screening; A1 storage; keeps screening cheap and isolated.
- *Files:* new `skills/screen-job/SKILL.md` (+ references); delete `tests/pipeline/test_screen_job.py`.
- *Deviation (decided during build):* `scripts/pipeline/screen_job.py` is **kept**, not deleted. It is still imported by the legacy Python orchestrator (`scraping_pipeline.py`, `add_job_by_url.py`, `screen_jobs_batch.py`), which the user parked ("non-jobs collections later"). Its `pb_client` import is lazy (inside the function), so the module still imports and the green test suite is unaffected; calling it would fail until that legacy path is retired. The new `screen-job` skill is the sanctioned path for the WellFound flow and does not touch `screen_job.py`. Only the dead, skip-only `tests/pipeline/test_screen_job.py` is removed.
- *Verify:* smoke run the skill on one real `enriched` WellFound job → read the job back via MCP and confirm `apply_verdict`, `relevance_score`, `one_line_summary`/`screen_summary` are populated and `status == "screened"`. Re-running the skill on a `screened` job does not duplicate or regress it.

### Phase 4 — Orchestration (depends on all above)

**T9 — Rewrite `wellfound-flow` as a DB-status sequencer.**
- *What:* rewrite the orchestrator skill to: run steps 1–10 in order; after each step check the exit code / outcome; on anything non-clean (no session, CDP down, bot-halt exit 2, missing MCP tool, any non-zero exit) **STOP and surface to the human** — never guess, never fall back to local DB writes. Remove all file-checkpoint language; resumability is "re-run me, I re-derive position from `status` in the DB". Use the single `status` field throughout. Each step is explicitly a script or the `screen-job` skill.
- *Why:* this is the human-gated, restartable orchestrator the whole plan is for.
- *Files:* `skills/wellfound-flow/SKILL.md` and the affected sub-skills.
- *Verify:* review pass + an end-to-end smoke on a tiny sample (`--limit`) confirming each step hands off to the next via DB status and that an injected failure (e.g. simulated bot-halt) stops the flow and asks for a human.

**T10 — Test/CI cleanup.**
- *What:* remove the quarantined `test_screen_job.py`, ensure all new step tests are collected, run the full suite.
- *Why:* keep the suite green and representative of the new design.
- *Files:* `tests/`.
- *Verify:* `pytest` from `agent/` is green (the pre-existing unrelated hirify failure is the only allowed exception, tracked separately).

### Phase 5 — Full-workflow validation (Sonnet subagent as the orchestrator)

This is the final acceptance stage. **Instead of Hermes, a Sonnet subagent plays the orchestrator** and runs the entire WellFound flow end-to-end against the live MCP (already connected).

**T11 — End-to-end dry/live run by a Sonnet subagent.**
- *What:* launch a subagent (model: Sonnet) whose job is to execute `wellfound-flow` exactly as written — step by step, reading/writing the DB only through MCP — on a small live sample. It must honour the human-gate: if it hits a bot-check or any non-clean step, it stops and reports rather than improvising.
- *Why:* proves the three layers work together: DB state machine + step scripts/skills + orchestrator behaviour, including resumability and the human-stop, before we hand it to Hermes.
- *Acceptance criteria (all must hold):*
  1. **Happy path:** starting from a clean sample, the subagent drives a handful of jobs `new → enriched → screened`, with each transition visible in the DB via MCP at the moment it happens (writes are incremental, not batched at the end).
  2. **Resumability:** kill the run after some jobs are `enriched` but before screening; wipe `tmp/`; re-launch the subagent. It must **not** re-enrich the already-`enriched` jobs and must resume at screening — verified by comparing DB timestamps / counts before and after.
  3. **No-rework:** no job is enriched twice or screened twice (check counts and that `enriched`/`screened` rows are never touched by the wrong step).
  4. **Human-gate:** when a bot-detection halt (or any non-zero step) occurs, the subagent stops and asks for a human; it does **not** advance the blocked job or fall back to local writes.
  5. **MCP-only:** the entire run touches the DB exclusively through MCP (no pb_client, no SQL) — confirmed by absence of any direct-DB code path.
- *Verify (per phase + together):* each prior phase has its own unit/smoke checks (above); Phase 5 verifies them **together** as one live workflow. Final sign-off = all five acceptance criteria pass on the Sonnet run.

---

## 8. Verification summary

| Phase | Verified in isolation by | Verified together by |
|-------|--------------------------|----------------------|
| 0 (T1) | round-trip `jobs_update` of new columns → 200 + readback | Phase 5 (screen writes land) |
| 1 (T2–T4) | grep=0, unit tests, row counts | Phase 5 (ingest → `new`) |
| 2 (T5–T7) | unit tests (fake browser + FakeMCPClient) | Phase 5 (enrich/fetch/dedup in the live run) |
| 3 (T8) | smoke on one real enriched job | Phase 5 (screen in the live run) |
| 4 (T9–T10) | review + injected-failure smoke; green suite | Phase 5 (orchestration drives the whole thing) |
| 5 (T11) | — | **the 5 acceptance criteria on a Sonnet end-to-end run** |

## 9. Risks / open items

- **Poison-pill jobs** (accepted for MVP) — see §4.
- **T4 normalisation rule** — decided: dirty rows → `new` (§6).
- **Prod schema change (T1)** touches the live PocketBase `jobs` collection; do it additively (new nullable columns only), never altering existing fields.
- **Cheap model quality for screen (T8)** — if the cheap model's verdicts are poor, bump the model; the skill boundary makes that a one-line change.

## 10. Task distribution

- **T1** — main thread (PB admin via MCP key), unblocks screen.
- **T2 / T3 / T4** — one subagent, parallel cleanup.
- **T5** — one subagent (enrich rework).
- **T6 / T7** — one subagent (small step scripts + tests).
- **T8** — one subagent (screen skill).
- **T9** — main thread, with Zall (design-heavy).
- **T11** — one **Sonnet** subagent acting as the orchestrator (Phase 5 validation).
