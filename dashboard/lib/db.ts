// Data access layer — PocketBase backend.
import { getServerPb } from './pb';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function esc(s: string): string {
  return s.replace(/\\/g, '\\\\').replace(/"/g, '\\"');
}

function parseJson<T>(val: unknown): T | null {
  if (val === null || val === undefined || val === '') return null;
  if (typeof val === 'string') {
    try { return JSON.parse(val) as T; } catch { return null; }
  }
  return val as T;
}

// PocketBase returns json-typed fields as already-parsed objects.
// Callers that expect JSON strings (InterviewsClient parseDates etc.) need strings back.
function ensureJsonString(val: unknown): string | null {
  if (val === null || val === undefined || val === '') return null;
  if (typeof val === 'string') return val;
  try { return JSON.stringify(val); } catch { return null; }
}

const INTERVIEW_JSON_FIELDS = ['interview_dates_json', 'contacts_json', 'emails_json'] as const;

function normalizeInterview(r: Record<string, unknown>): Record<string, unknown> {
  const out = { ...r };
  for (const f of INTERVIEW_JSON_FIELDS) {
    out[f] = ensureJsonString(out[f]);
  }
  return out;
}

// ---------------------------------------------------------------------------
// Types (id is string — PocketBase IDs)
// ---------------------------------------------------------------------------

export type Job = {
  id: string;
  url: string;
  provider: string;
  posted_company_name: string | null;
  title: string | null;
  location: string | null;
  country: string | null;
  remote_scope: string | null;
  status: string;
  pipeline_status: string;
  user_status: string | null;
  research_status: string | null;
  comment: string | null;
  first_seen: string;
  last_seen: string;
  company_id: string | null;
  apply_url: string | null;
  description: string | null;
  source_payload_json: string | null;
};

export type JobAssessment = {
  id: string;
  job_id: string;
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
  id: string;
  company_id: string;
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
  id: string;
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
  status?: string;
  user_status?: string;
  provider?: string;
  country?: string;
  remote_scope?: string;
  unresearched?: boolean;
  new_only?: boolean;
  apply_verdict?: string;
};

export type Contact = Record<string, string | undefined>;

export type EmailMessage = {
  from?: string;
  date?: string;
  subject?: string;
  body: string;
};

export type InterviewDate = {
  date: string;
  label?: string;
  url?: string;
};

export type Interview = {
  id: string;
  company_name: string | null;
  job_title: string | null;
  status: string | null;
  interview_status: string | null;
  next_interview_date: string | null;
  interview_dates_json: string | null;
  description: string | null;
  contacts: string | null;
  contact_via: string | null;
  telegram_handle: string | null;
  job_url: string | null;
  comments: string | null;
  contacts_json: string | null;
  emails_json: string | null;
  job_id: string | null;
  created_at: string;
  updated_at: string;
};

// ---------------------------------------------------------------------------
// listJobs
// ---------------------------------------------------------------------------

export async function listJobs(filters: JobFilters = {}): Promise<(Job & {
  relevance_score: number | null;
  apply_verdict: string | null;
  trustworthiness_score: number | null;
  is_researching: number;
  is_scraping: number;
})[]> {
  const pb = getServerPb();

  const conditions: string[] = ['deleted_at = null'];
  if (filters.status)       conditions.push(`pipeline_status = "${esc(filters.status)}"`);
  if (filters.user_status)  conditions.push(`user_status = "${esc(filters.user_status)}"`);
  if (filters.provider)     conditions.push(`provider = "${esc(filters.provider)}"`);
  if (filters.country)      conditions.push(`country = "${esc(filters.country)}"`);
  if (filters.remote_scope) conditions.push(`remote_scope = "${esc(filters.remote_scope)}"`);
  if (filters.new_only)     conditions.push('pipeline_status = "new"');

  const thirtyAgo = new Date(Date.now() - 30 * 60 * 1000)
    .toISOString().replace('T', ' ').slice(0, 19);

  const [jobsResult, allAssessments, allResearch, activeCommands] = await Promise.all([
    pb.collection('jobs').getList(1, 500, { filter: conditions.join(' && ') }),
    pb.collection('job_assessments').getFullList({ batch: 500 }),
    pb.collection('company_research').getFullList({ batch: 200 }),
    pb.collection('agent_commands').getFullList({
      batch: 200,
      filter: `(status = "pending" || status = "running") && created_at >= "${thirtyAgo}"`,
    }),
  ]);

  const assessmentMap = new Map(allAssessments.map(a => [a['job_id'] as string, a]));
  const researchMap   = new Map(allResearch.map(r => [r['company_id'] as string, r]));

  const researchingIds = new Set<string>();
  const scrapingIds    = new Set<string>();
  for (const cmd of activeCommands) {
    const payload = parseJson<{ job_id?: string | number }>(cmd['payload_json']);
    if (!payload?.job_id) continue;
    const jid = String(payload.job_id).padStart(15, '0');
    if (cmd['command_type'] === 'research_job') researchingIds.add(jid);
    if (cmd['command_type'] === 'scrape_job')   scrapingIds.add(jid);
  }

  const results: ReturnType<typeof listJobs> extends Promise<infer R> ? R : never = [];

  for (const j of jobsResult.items) {
    const assessment = assessmentMap.get(j['id'] as string);

    if (assessment?.['apply_verdict'] === 'Skip') continue;
    if (filters.unresearched && assessment) continue;
    if (filters.apply_verdict && assessment?.['apply_verdict'] !== filters.apply_verdict) continue;

    const companyId = j['company_id'] as string | null;
    const research  = companyId ? researchMap.get(companyId) ?? null : null;

    results.push({
      ...(j as unknown as Job),
      relevance_score:       (assessment?.['relevance_score'] as number | null) ?? null,
      apply_verdict:         (assessment?.['apply_verdict']   as string | null) ?? null,
      trustworthiness_score: (research?.['trustworthiness_score'] as number | null) ?? null,
      is_researching: researchingIds.has(j['id'] as string) ? 1 : 0,
      is_scraping:    scrapingIds.has(j['id'] as string)    ? 1 : 0,
    });
  }

  const usPriority: Record<string, number> = { offer: 0, interviewing: 1, applied: 2, interesting: 3 };
  results.sort((a, b) => {
    const du = (usPriority[a.user_status ?? ''] ?? 10) - (usPriority[b.user_status ?? ''] ?? 10);
    if (du !== 0) return du;
    const dp = (a.pipeline_status === 'new' ? 0 : 1) - (b.pipeline_status === 'new' ? 0 : 1);
    if (dp !== 0) return dp;
    const dr = (b.relevance_score ?? 0) - (a.relevance_score ?? 0);
    if (dr !== 0) return dr;
    const dt = (b.trustworthiness_score ?? 0) - (a.trustworthiness_score ?? 0);
    if (dt !== 0) return dt;
    return (b.first_seen ?? '').localeCompare(a.first_seen ?? '');
  });

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  return results as any;
}

// ---------------------------------------------------------------------------
// getJobDetail
// ---------------------------------------------------------------------------

export async function getJobDetail(id: string): Promise<{
  job: Job;
  assessment: JobAssessment | null;
  research: CompanyResearch | null;
  commands: AgentCommand[];
} | null> {
  const pb = getServerPb();
  try {
    const job = await pb.collection('jobs').getOne(id);

    const [assessmentsResult, commandsResult] = await Promise.all([
      pb.collection('job_assessments').getList(1, 1, { filter: `job_id = "${esc(id)}"` }),
      pb.collection('agent_commands').getList(1, 10, {
        sort: '-created_at',
        filter: `(command_type = "research_job" || command_type = "scrape_job" || command_type = "screen_job")`,
      }),
    ]);

    // Filter commands by job_id in memory (handles both string and integer stored values)
    const numId = parseInt(id);
    const relatedCommands = commandsResult.items.filter(cmd => {
      const p = parseJson<{ job_id?: string | number }>(cmd['payload_json']);
      if (!p?.job_id) return false;
      const pStr = String(p.job_id).padStart(15, '0');
      return pStr === id || (Number.isFinite(numId) && Number(p.job_id) === numId);
    });

    const assessment = assessmentsResult.items[0] ?? null;
    let research: CompanyResearch | null = null;
    const companyId = job['company_id'] as string | null;
    if (companyId) {
      const resResult = await pb.collection('company_research').getList(1, 1, {
        filter: `company_id = "${esc(companyId)}"`,
      });
      research = (resResult.items[0] ?? null) as unknown as CompanyResearch | null;
    }

    return {
      job:        job as unknown as Job,
      assessment: assessment as unknown as JobAssessment | null,
      research,
      commands:   relatedCommands as unknown as AgentCommand[],
    };
  } catch {
    return null;
  }
}

// ---------------------------------------------------------------------------
// addManualJob
// ---------------------------------------------------------------------------

export async function addManualJob(url: string): Promise<{ id: string; created: boolean }> {
  const pb = getServerPb();
  const existing = await pb.collection('jobs').getList(1, 1, { filter: `url = "${esc(url)}"` });
  if (existing.items.length > 0) return { id: existing.items[0]['id'] as string, created: false };

  const record = await pb.collection('jobs').create({
    url,
    provider: 'manual',
    status: 'new',
    pipeline_status: 'new',
    first_seen: new Date().toISOString().replace('T', ' ').slice(0, 19),
    last_seen:  new Date().toISOString().replace('T', ' ').slice(0, 19),
  });
  await pb.collection('events').create({
    entity_type: 'job',
    entity_id:   record['id'],
    event_type:  'job_inserted',
    actor:       'ui',
    created_at:  new Date().toISOString().replace('T', ' ').slice(0, 19),
  });
  return { id: record['id'] as string, created: true };
}

// ---------------------------------------------------------------------------
// updateJobWorkflowFields
// ---------------------------------------------------------------------------

export async function updateJobWorkflowFields(
  id: string,
  fields: { user_status?: string; comment?: string },
): Promise<void> {
  const pb = getServerPb();
  const data: Record<string, string> = { updated_at: new Date().toISOString().replace('T', ' ').slice(0, 19) };
  if (fields.user_status !== undefined) data['user_status'] = fields.user_status;
  if (fields.comment     !== undefined) data['comment']     = fields.comment;
  await pb.collection('jobs').update(id, data);
}

// ---------------------------------------------------------------------------
// softDeleteJob
// ---------------------------------------------------------------------------

export async function softDeleteJob(id: string): Promise<void> {
  const pb = getServerPb();
  const now = new Date().toISOString().replace('T', ' ').slice(0, 19);
  await pb.collection('jobs').update(id, { deleted_at: now, updated_at: now });
}

// ---------------------------------------------------------------------------
// Command helpers
// ---------------------------------------------------------------------------

async function findPendingCommand(commandType: string, jobId: string): Promise<string | null> {
  const pb = getServerPb();
  const numId = parseInt(jobId);
  const filter = `command_type = "${commandType}" && (status = "pending" || status = "running")`;
  const result = await pb.collection('agent_commands').getList(1, 50, { filter });
  const match = result.items.find(cmd => {
    const p = parseJson<{ job_id?: string | number }>(cmd['payload_json']);
    if (!p?.job_id) return false;
    const pStr = String(p.job_id).padStart(15, '0');
    return pStr === jobId || (Number.isFinite(numId) && Number(p.job_id) === numId);
  });
  return match ? (match['id'] as string) : null;
}

async function createCommand(commandType: string, jobId: string, extra: Record<string, unknown> = {}): Promise<{ commandId: string; existing: boolean }> {
  const pb = getServerPb();
  const existingId = await findPendingCommand(commandType, jobId);
  if (existingId) return { commandId: existingId, existing: true };

  const numId = parseInt(jobId);
  const record = await pb.collection('agent_commands').create({
    command_type: commandType,
    payload_json: JSON.stringify({ job_id: Number.isFinite(numId) ? numId : jobId, ...extra }),
    status: 'pending',
    created_by: 'ui',
    created_at: new Date().toISOString().replace('T', ' ').slice(0, 19),
  });
  return { commandId: record['id'] as string, existing: false };
}

export async function createScrapeCommand(jobId: string, url: string): Promise<{ commandId: string; existing: boolean }> {
  return createCommand('scrape_job', jobId, { url });
}

export async function createResearchCommand(jobId: string): Promise<{ commandId: string; existing: boolean }> {
  return createCommand('research_job', jobId);
}

export async function createScreenCommand(jobId: string): Promise<{ commandId: string; existing: boolean }> {
  return createCommand('screen_job', jobId);
}

export async function markCommandFailed(commandId: string, error: string): Promise<void> {
  const pb = getServerPb();
  await pb.collection('agent_commands').update(commandId, {
    status: 'failed',
    error,
    finished_at: new Date().toISOString().replace('T', ' ').slice(0, 19),
  });
}

export async function getCommand(commandId: string): Promise<AgentCommand | null> {
  const pb = getServerPb();
  try {
    const r = await pb.collection('agent_commands').getOne(commandId);
    return r as unknown as AgentCommand;
  } catch { return null; }
}

// ---------------------------------------------------------------------------
// Interviews
// ---------------------------------------------------------------------------

const INTERVIEW_SORT: Record<string, number> = { offer: 0, in_process: 1, applied: 2, rejected: 9 };

export async function listInterviews(): Promise<Interview[]> {
  const pb = getServerPb();
  const items = await pb.collection('interviews').getFullList({ batch: 200 });
  return (items.map(r => normalizeInterview(r as unknown as Record<string, unknown>)) as unknown as Interview[]).sort((a, b) => {
    const ds = (INTERVIEW_SORT[a.status ?? ''] ?? 5) - (INTERVIEW_SORT[b.status ?? ''] ?? 5);
    if (ds !== 0) return ds;
    const nd = (a.next_interview_date ?? 'zzz').localeCompare(b.next_interview_date ?? 'zzz');
    if (nd !== 0) return nd;
    return (b.created_at ?? '').localeCompare(a.created_at ?? '');
  });
}

export async function createInterview(): Promise<Interview> {
  const pb = getServerPb();
  const now = new Date().toISOString().replace('T', ' ').slice(0, 19);
  const r = await pb.collection('interviews').create({ status: 'applied', created_at: now, updated_at: now });
  return normalizeInterview(r as unknown as Record<string, unknown>) as unknown as Interview;
}

export async function updateInterview(
  id: string,
  data: Partial<Omit<Interview, 'id' | 'created_at' | 'updated_at'>>,
): Promise<Interview | null> {
  const pb = getServerPb();
  try {
    const r = await pb.collection('interviews').update(id, {
      ...data,
      updated_at: new Date().toISOString().replace('T', ' ').slice(0, 19),
    });
    return normalizeInterview(r as unknown as Record<string, unknown>) as unknown as Interview;
  } catch { return null; }
}

export async function deleteInterview(id: string): Promise<void> {
  const pb = getServerPb();
  await pb.collection('interviews').delete(id);
}
