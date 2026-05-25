// Server-only SQLite access. Never import this in client components.
import Database from "better-sqlite3";
import path from "path";

const DB_PATH = path.resolve(process.cwd(), "../jobs.db");

let _db: Database.Database | null = null;

export function getDb(): Database.Database {
  if (!_db) {
    _db = new Database(DB_PATH, { readonly: false });
    _db.pragma("foreign_keys = ON");
    _db.pragma("journal_mode = WAL");
  }
  return _db;
}

export type Job = {
  id: number;
  url: string;
  provider: string;
  posted_company_name: string | null;
  title: string | null;
  location: string | null;
  country: string | null;
  remote_scope: string | null;
  status: string;               // legacy — still in DB, kept for compat
  pipeline_status: string;      // new
  user_status: string | null;   // new
  research_status: string | null; // new
  comment: string | null;
  first_seen: string;
  last_seen: string;
  company_id: number | null;
  apply_url: string | null;
  description: string | null;
  source_payload_json: string | null;
};

export type JobAssessment = {
  id: number;
  job_id: number;
  assessment_status: string;
  relevance_score: number | null;
  apply_verdict: string | null;
  one_line_summary: string | null;
  red_flag_scan: string | null;
  seniority_fit: string | null;
  tech_stack_fit: string | null;
  salary_assessment: string | null;
  remote_eligibility: string | null;
  assessed_at: string | null;
};

export type CompanyResearch = {
  id: number;
  company_id: number;
  trustworthiness_score: number | null;
  research_status: string;
  legitimacy_check: string | null;
  hiring_entity_type: string | null;
  glassdoor_summary: string | null;
  funding_summary: string | null;
  research_notes: string | null;
  researched_at: string | null;
};

export type AgentCommand = {
  id: number;
  command_type: string;
  payload_json: string | null;
  status: string;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  result_json: string | null;
  error: string | null;
};

export type JobFilters = {
  status?: string;           // maps to pipeline_status
  user_status?: string;      // new
  provider?: string;
  country?: string;
  remote_scope?: string;
  unresearched?: boolean;
  new_only?: boolean;
  apply_verdict?: string;
};

export function listJobs(filters: JobFilters = {}): (Job & {
  relevance_score: number | null;
  apply_verdict: string | null;
  trustworthiness_score: number | null;
  is_researching: number;
  is_scraping: number;
})[] {
  const db = getDb();
  const conditions: string[] = [
    "j.deleted_at IS NULL",
    "(ja.apply_verdict != 'Skip' OR ja.apply_verdict IS NULL)",
  ];
  const params: unknown[] = [];

  if (filters.status) { conditions.push("j.pipeline_status = ?"); params.push(filters.status); }
  if (filters.user_status) { conditions.push("j.user_status = ?"); params.push(filters.user_status); }
  if (filters.provider) { conditions.push("j.provider = ?"); params.push(filters.provider); }
  if (filters.country) { conditions.push("j.country = ?"); params.push(filters.country); }
  if (filters.remote_scope) { conditions.push("j.remote_scope = ?"); params.push(filters.remote_scope); }
  if (filters.unresearched) { conditions.push("ja.id IS NULL"); }
  if (filters.new_only) { conditions.push("j.pipeline_status = 'new'"); }
  if (filters.apply_verdict) { conditions.push("ja.apply_verdict = ?"); params.push(filters.apply_verdict); }

  const where = conditions.length ? `WHERE ${conditions.join(" AND ")}` : "";
  const sql = `
    SELECT j.*,
           ja.relevance_score, ja.apply_verdict,
           cr.trustworthiness_score,
           CASE WHEN rc.job_id IS NOT NULL THEN 1 ELSE 0 END AS is_researching,
           CASE WHEN sc.job_id IS NOT NULL THEN 1 ELSE 0 END AS is_scraping
    FROM jobs j
    LEFT JOIN job_assessments ja ON ja.job_id = j.id
    LEFT JOIN company_research cr ON cr.company_id = j.company_id
    LEFT JOIN (
      SELECT DISTINCT CAST(json_extract(payload_json, '$.job_id') AS INTEGER) AS job_id
      FROM agent_commands
      WHERE command_type = 'research_job' AND status IN ('pending', 'running') AND json_valid(payload_json)
        AND created_at >= datetime('now', '-30 minutes')
    ) rc ON rc.job_id = j.id
    LEFT JOIN (
      SELECT DISTINCT CAST(json_extract(payload_json, '$.job_id') AS INTEGER) AS job_id
      FROM agent_commands
      WHERE command_type = 'scrape_job' AND status IN ('pending', 'running') AND json_valid(payload_json)
        AND created_at >= datetime('now', '-30 minutes')
    ) sc ON sc.job_id = j.id
    ${where}
    ORDER BY
      CASE j.user_status
        WHEN 'offer'        THEN 0
        WHEN 'interviewing' THEN 1
        WHEN 'applied'      THEN 2
        WHEN 'interesting'  THEN 3
        ELSE 10
      END,
      CASE j.pipeline_status WHEN 'new' THEN 0 ELSE 1 END,
      COALESCE(ja.relevance_score, 0) DESC,
      COALESCE(cr.trustworthiness_score, 0) DESC,
      j.first_seen DESC
    LIMIT 500
  `;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  return db.prepare(sql).all(...params) as any;
}

export function getJobDetail(id: number): {
  job: Job;
  assessment: JobAssessment | null;
  research: CompanyResearch | null;
  commands: AgentCommand[];
} | null {
  const db = getDb();
  const job = db.prepare("SELECT * FROM jobs WHERE id = ?").get(id) as Job | undefined;
  if (!job) return null;
  const assessment = db.prepare("SELECT * FROM job_assessments WHERE job_id = ?").get(id) as JobAssessment | null;
  const research = job.company_id
    ? db.prepare("SELECT * FROM company_research WHERE company_id = ?").get(job.company_id) as CompanyResearch | null
    : null;
  const commands = db.prepare(
    "SELECT * FROM agent_commands WHERE json_valid(payload_json) AND json_extract(payload_json, '$.job_id') = ? ORDER BY created_at DESC LIMIT 10"
  ).all(id) as AgentCommand[];
  return { job, assessment, research, commands };
}

export function addManualJob(url: string): { id: number; created: boolean } {
  const db = getDb();
  const existing = db.prepare("SELECT id FROM jobs WHERE url = ?").get(url) as { id: number } | undefined;
  if (existing) return { id: existing.id, created: false };
  const result = db.prepare(
    "INSERT INTO jobs (url, provider, status) VALUES (?, 'manual', 'new')"
  ).run(url);
  const id = result.lastInsertRowid as number;
  db.prepare(
    "INSERT INTO events (entity_type, entity_id, event_type, actor) VALUES ('job', ?, 'job_inserted', 'ui')"
  ).run(id);
  return { id, created: true };
}

export function updateJobWorkflowFields(
  id: number,
  fields: { user_status?: string; comment?: string }
): void {
  const db = getDb();
  const updates: string[] = [];
  const params: unknown[] = [];
  if (fields.user_status !== undefined) { updates.push("user_status = ?"); params.push(fields.user_status); }
  if (fields.comment !== undefined) { updates.push("comment = ?"); params.push(fields.comment); }
  if (!updates.length) return;
  updates.push("updated_at = datetime('now')");
  params.push(id);
  db.prepare(`UPDATE jobs SET ${updates.join(", ")} WHERE id = ?`).run(...params);
}

export function softDeleteJob(id: number): void {
  const db = getDb();
  db.prepare("UPDATE jobs SET deleted_at = datetime('now'), updated_at = datetime('now') WHERE id = ?").run(id);
}

export function createScrapeCommand(jobId: number, url: string): { commandId: number; existing: boolean } {
  const db = getDb();
  const existing = db.prepare(
    "SELECT id FROM agent_commands WHERE command_type = 'scrape_job' AND status IN ('pending','running') AND json_extract(payload_json,'$.job_id') = ?"
  ).get(jobId) as { id: number } | undefined;
  if (existing) return { commandId: existing.id, existing: true };
  const result = db.prepare(
    "INSERT INTO agent_commands (command_type, payload_json, status, created_by) VALUES ('scrape_job', ?, 'pending', 'ui')"
  ).run(JSON.stringify({ job_id: jobId, url }));
  return { commandId: result.lastInsertRowid as number, existing: false };
}

export function createResearchCommand(jobId: number): { commandId: number; existing: boolean } {
  const db = getDb();
  const existing = db.prepare(
    "SELECT id FROM agent_commands WHERE command_type = 'research_job' AND status IN ('pending','running') AND json_extract(payload_json,'$.job_id') = ?"
  ).get(jobId) as { id: number } | undefined;
  if (existing) return { commandId: existing.id, existing: true };
  const result = db.prepare(
    "INSERT INTO agent_commands (command_type, payload_json, status, created_by) VALUES ('research_job', ?, 'pending', 'ui')"
  ).run(JSON.stringify({ job_id: jobId }));
  return { commandId: result.lastInsertRowid as number, existing: false };
}

export function createScreenCommand(jobId: number): { commandId: number; existing: boolean } {
  const db = getDb();
  const existing = db.prepare(
    "SELECT id FROM agent_commands WHERE command_type = 'screen_job' AND status IN ('pending','running') AND json_extract(payload_json,'$.job_id') = ?"
  ).get(jobId) as { id: number } | undefined;
  if (existing) return { commandId: existing.id, existing: true };
  const result = db.prepare(
    "INSERT INTO agent_commands (command_type, payload_json, status, created_by) VALUES ('screen_job', ?, 'pending', 'ui')"
  ).run(JSON.stringify({ job_id: jobId }));
  return { commandId: result.lastInsertRowid as number, existing: false };
}

export function createApplyCommand(jobId: number): { commandId: number; existing: boolean } {
  const db = getDb();
  const existing = db.prepare(
    "SELECT id FROM agent_commands WHERE command_type = 'apply_job' AND status IN ('pending','running') AND json_extract(payload_json,'$.job_id') = ?"
  ).get(jobId) as { id: number } | undefined;
  if (existing) return { commandId: existing.id, existing: true };
  const result = db.prepare(
    "INSERT INTO agent_commands (command_type, payload_json, status, created_by) VALUES ('apply_job', ?, 'pending', 'ui')"
  ).run(JSON.stringify({ job_id: jobId }));
  return { commandId: result.lastInsertRowid as number, existing: false };
}
