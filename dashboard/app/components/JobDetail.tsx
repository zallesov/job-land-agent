"use client";
import { useEffect, useState } from "react";
import PocketBase from "pocketbase";
import { CommandButton } from "./CommandButton";
import { PROVIDER_COLORS } from "./JobList";
import { PB_URL } from "@/lib/pb";

const USER_STATUSES = ["interesting","not_interesting","applied","rejected","interviewing","offer"];

const USER_STATUS_LABELS: Record<string, string> = {
  interesting:     "Interesting",
  not_interesting: "Not Interesting",
  applied:         "Applied",
  rejected:        "Rejected",
  interviewing:    "Interviewing",
  offer:           "Offer",
};

const PIPELINE_STATUS_LABELS: Record<string, string> = {
  new:            "New",
  enriched:       "Enriched",
  screened:       "Screened",
  enrich_failed:  "Enrich Failed",
  screen_failed:  "Screen Failed",
};

const PIPELINE_STATUS_ACCENT: Record<string, string> = {
  new:            "#94a3b8",
  enriched:       "#60a5fa",
  screened:       "#34d399",
  enrich_failed:  "#ef4444",
  screen_failed:  "#f97316",
};

const USER_STATUS_ACCENT: Record<string, string> = {
  interesting:     "#4ade80",
  not_interesting: "#475569",
  applied:         "#818cf8",
  rejected:        "#f87171",
  interviewing:    "#2dd4bf",
  offer:           "#c084fc",
};


const VERDICT_CONFIG: Record<string, { bg: string; accent: string; label: string; labelColor: string }> = {
  "Strong Apply":       { bg: "var(--green-bg)",  accent: "var(--green)",        label: "STRONG APPLY",       labelColor: "var(--green)" },
  "Apply with Caution": { bg: "var(--amber-bg)",  accent: "var(--amber)",        label: "APPLY WITH CAUTION", labelColor: "var(--amber)" },
  "Need Research":      { bg: "rgba(96,165,250,0.10)", accent: "#60a5fa",        label: "NEED RESEARCH",      labelColor: "#60a5fa" },
  "Skip":               { bg: "var(--red-bg)",    accent: "var(--red-border)",   label: "SKIP",               labelColor: "var(--text-2)" },
};
const DEFAULT_VERDICT = { bg: "var(--surface)", accent: "var(--border-hi)", label: "NOT SCREENED", labelColor: "var(--text-3)" };

function FieldLabel({ children }: { children: React.ReactNode }) {
  return (
    <div style={{
      fontFamily: "var(--font-mono, 'SF Mono', 'Fira Code', monospace)",
      fontSize: 9,
      fontWeight: 600,
      letterSpacing: "0.14em",
      textTransform: "uppercase",
      color: "var(--text-3)",
      marginBottom: 5,
    }}>
      {children}
    </div>
  );
}

function ScoreBlock({ label, value, color }: { label: string; value: number | null | undefined; color: string }) {
  if (value == null) return null;
  return (
    <div className="flex flex-col items-center" style={{ minWidth: 40 }}>
      <span className="font-data text-xs font-medium tracking-widest uppercase" style={{ color: "var(--text-3)", fontSize: 9 }}>{label}</span>
      <span className="font-data font-semibold leading-none" style={{ color, fontSize: 26 }}>{value}</span>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string | number | null | undefined }) {
  if (value == null || value === "" || value === "Not found") return null;
  return (
    <div className="flex gap-2 text-xs leading-relaxed">
      <span className="shrink-0 font-medium" style={{ color: "var(--text-3)", width: 90 }}>{label}</span>
      <span style={{ color: "var(--text-1)" }}>{String(value)}</span>
    </div>
  );
}

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <div className="font-data text-xs font-semibold tracking-widest uppercase mb-3"
      style={{ color: "var(--text-3)", letterSpacing: "0.12em" }}>
      {children}
    </div>
  );
}

export function JobDetail({ jobId, updateJobAction, onDelete }: {
  jobId: string;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  updateJobAction: (id: string, fields: any) => Promise<void>;
  onDelete?: () => void;
}) {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const [data, setData] = useState<any | null>(null);
  const [loading, setLoading] = useState(true);
  const [editingNote, setEditingNote] = useState(false);
  const [noteValue, setNoteValue] = useState("");
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [screening, setScreening] = useState(false);
  const [currentUserStatus, setCurrentUserStatus] = useState<string | null>(null);
  const [currentPipelineStatus, setCurrentPipelineStatus] = useState<string>("new");
  const [currentResearchStatus, setCurrentResearchStatus] = useState<string | null>(null);

  const load = () => {
    setLoading(true);
    fetch(`/api/jobs/${jobId}`)
      .then(r => r.json())
      .then(d => {
        setData(d);
        setNoteValue(d.job?.comment ?? "");
        setCurrentUserStatus(d.job?.user_status ?? null);
        setCurrentPipelineStatus(d.job?.pipeline_status ?? "new");
        setCurrentResearchStatus(d.job?.research_status ?? null);
      })
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, [jobId]); // eslint-disable-line react-hooks/exhaustive-deps

  // Realtime: keep this job's detail view live without manual refresh.
  useEffect(() => {
    const pb = new PocketBase(PB_URL);
    pb.authStore.loadFromCookie(document.cookie);

    pb.collection('jobs').subscribe(jobId, () => load()).catch(() => {});

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    pb.collection('job_assessments').subscribe('*', (e: any) => {
      if (e.record['job_id'] === jobId) load();
    }).catch(() => {});

    pb.collection('company_research').subscribe('*', () => load()).catch(() => {});

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    pb.collection('agent_commands').subscribe('*', (e: any) => {
      const payload = e.record['payload_json'];
      const p = typeof payload === 'string' ? (() => { try { return JSON.parse(payload); } catch { return null; } })() : payload;
      if (p?.job_id != null && String(p.job_id).padStart(15, '0') === jobId) load();
    }).catch(() => {});

    return () => {
      pb.collection('jobs').unsubscribe(jobId).catch(() => {});
      pb.collection('job_assessments').unsubscribe('*').catch(() => {});
      pb.collection('company_research').unsubscribe('*').catch(() => {});
      pb.collection('agent_commands').unsubscribe('*').catch(() => {});
    };
  }, [jobId]); // eslint-disable-line react-hooks/exhaustive-deps

  if (loading) return (
    <div className="flex items-center justify-center h-32">
      <span className="font-data text-xs animate-pulse" style={{ color: "var(--text-3)" }}>loading…</span>
    </div>
  );
  if (!data?.job) return <div className="p-6 text-sm" style={{ color: "var(--red)" }}>Job not found</div>;

  const { job, assessment, research, commands } = data;
  const verdict = VERDICT_CONFIG[assessment?.apply_verdict ?? ""] ?? DEFAULT_VERDICT;
  const accent = USER_STATUS_ACCENT[currentUserStatus ?? ""]
    ?? PIPELINE_STATUS_ACCENT[currentPipelineStatus]
    ?? "#475569";

  async function handleUserStatusChange(val: string) {
    setCurrentUserStatus(val);
    await updateJobAction(jobId, { user_status: val });
  }

async function saveNote() {
    setSaving(true);
    await updateJobAction(jobId, { comment: noteValue });
    setEditingNote(false);
    setSaving(false);
    load();
  }

  async function handleDelete() {
    setDeleting(true);
    await fetch(`/api/jobs/${jobId}`, { method: "DELETE" });
    onDelete?.();
  }

  async function handleScreen() {
    setScreening(true);
    try {
      await fetch("/api/commands", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ command_type: "screen_job", job_id: jobId }),
      });
      load();
    } finally {
      setScreening(false);
    }
  }

  return (
    <div style={{ maxWidth: 820, margin: "0 auto", paddingBottom: 48 }}>

      {/* ── ZONE 1: Meta strip ── */}
      <div style={{
        display: "flex",
        alignItems: "center",
        gap: 10,
        padding: "10px 24px",
        borderBottom: "1px solid var(--border)",
        flexWrap: "wrap",
      }}>
        <span className="font-data font-bold" style={{ color: "var(--text-1)", fontSize: 13 }}>#{job.id}</span>
        {job.provider && (
          <span className="font-data text-xs px-1.5 py-px rounded"
            style={{
              background: PROVIDER_COLORS[job.provider]?.bg ?? "var(--surface-hi)",
              color: PROVIDER_COLORS[job.provider]?.color ?? "var(--text-3)",
            }}>
            {job.provider}
          </span>
        )}
        <span style={{ color: "var(--border-hi)" }}>·</span>
        <span className="font-data text-xs" style={{ color: "var(--text-3)" }}>
          Seen {job.first_seen?.slice(0, 10)}
        </span>
        {job.date_posted && <>
          <span style={{ color: "var(--border-hi)" }}>·</span>
          <span className="font-data text-xs" style={{ color: "var(--text-3)" }}>{job.date_posted}</span>
        </>}
        <span style={{ color: "var(--border-hi)" }}>·</span>
        <a href={job.url} target="_blank" rel="noopener noreferrer"
          className="font-data text-xs font-medium transition-opacity hover:opacity-70"
          style={{ color: "var(--blue)" }}>
          Posting ↗
        </a>
        {job.apply_url && job.apply_url !== job.url && (
          <a href={job.apply_url} target="_blank" rel="noopener noreferrer"
            className="font-data text-xs font-medium transition-opacity hover:opacity-70"
            style={{ color: "var(--green)" }}>
            Apply ↗
          </a>
        )}
        <div style={{ marginLeft: "auto", display: "flex", gap: 8, alignItems: "center" }}>
          {(currentPipelineStatus === "enriched" || currentPipelineStatus === "new" || currentPipelineStatus === "screen_failed") && (
            <button onClick={handleScreen} disabled={screening}
              className="font-data text-xs font-medium rounded px-3 py-1 transition-colors disabled:opacity-40"
              style={{ background: "var(--amber)", color: "#000" }}>
              {screening ? "…" : "Screen"}
            </button>
          )}
          {confirmDelete ? (
            <div className="flex items-center gap-1">
              <span className="font-data text-xs" style={{ color: "var(--text-3)" }}>delete?</span>
              <button type="button" onClick={handleDelete} disabled={deleting}
                className="font-data text-xs rounded px-2 py-1 disabled:opacity-40"
                style={{ background: "var(--red)", color: "#fff" }}>
                {deleting ? "…" : "yes"}
              </button>
              <button type="button" onClick={() => setConfirmDelete(false)}
                className="font-data text-xs rounded px-2 py-1"
                style={{ color: "var(--text-2)", border: "1px solid var(--border-hi)" }}>
                no
              </button>
            </div>
          ) : (
            <button type="button" onClick={() => setConfirmDelete(true)}
              className="font-data text-xs rounded px-2 py-1 transition-colors"
              style={{ color: "var(--text-3)", border: "1px solid var(--border)" }}>
              Delete
            </button>
          )}
        </div>
      </div>

      {/* ── ZONE 2: Title block + status accent ── */}
      <div style={{
        borderLeft: `3px solid ${accent}`,
        padding: "18px 22px",
        borderBottom: "1px solid var(--border)",
        transition: "border-color 0.2s ease",
      }}>
        <h1 style={{
          color: "var(--text-1)",
          fontSize: 22,
          fontWeight: 700,
          lineHeight: 1.25,
          marginBottom: 6,
          letterSpacing: "-0.01em",
        }}>
          {job.title ?? "(no title)"}
        </h1>
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-sm font-semibold" style={{ color: "var(--text-2)" }}>
            {job.posted_company_name}
          </span>
          {job.country && <><span style={{ color: "var(--border-hi)" }}>·</span><span className="text-sm" style={{ color: "var(--text-2)" }}>{job.country}</span></>}
          {job.remote_scope && <><span style={{ color: "var(--border-hi)" }}>·</span><span className="text-sm" style={{ color: "var(--text-2)" }}>{job.remote_scope}</span></>}
          {(job.salary_range || assessment?.salary_assessment) && (
            <span className="font-data text-xs px-2 py-0.5 rounded"
              style={{ background: "var(--surface-hi)", color: "var(--text-1)", border: "1px solid var(--border-hi)" }}>
              {job.salary_range || assessment?.salary_assessment}
            </span>
          )}
        </div>
      </div>

      {/* ── ZONE 3: Status command bar ── */}
      <div style={{
        display: "grid",
        gridTemplateColumns: "auto auto auto auto 1fr",
        gap: 0,
        borderBottom: `2px solid ${accent}`,
        background: "var(--surface-hi)",
        transition: "border-color 0.2s ease",
      }}>
        {/* Pipeline (read-only) */}
        <div style={{ padding: "12px 20px", borderRight: "1px solid var(--border)" }}>
          <FieldLabel>Pipeline</FieldLabel>
          <span style={{
            fontFamily: "var(--font-mono, 'SF Mono', monospace)",
            fontWeight: 700,
            fontSize: 13,
            color: PIPELINE_STATUS_ACCENT[currentPipelineStatus] ?? "#475569",
          }}>
            {PIPELINE_STATUS_LABELS[currentPipelineStatus] ?? currentPipelineStatus}
          </span>
        </div>

        {/* User Status (editable dropdown) */}
        <div style={{ padding: "12px 20px", borderRight: "1px solid var(--border)" }}>
          <FieldLabel>Status</FieldLabel>
          <select
            value={currentUserStatus ?? ""}
            onChange={e => handleUserStatusChange(e.target.value)}
            className="text-xs rounded outline-none transition-colors"
            style={{
              background: "transparent",
              border: "none",
              color: currentUserStatus
                ? (USER_STATUS_ACCENT[currentUserStatus] ?? "var(--text-2)")
                : "var(--text-3)",
              fontFamily: "var(--font-mono, 'SF Mono', monospace)",
              fontWeight: currentUserStatus ? 700 : 400,
              fontSize: 13,
              cursor: "pointer",
              padding: "2px 14px 2px 0",
              appearance: "none",
              WebkitAppearance: "none",
              backgroundImage: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='10' height='6' viewBox='0 0 10 6'%3E%3Cpath fill='%23475569' d='M5 6L0 0h10z'/%3E%3C/svg%3E")`,
              backgroundRepeat: "no-repeat",
              backgroundPosition: "right 0 center",
            }}>
            <option value="" disabled>— set status —</option>
            {USER_STATUSES.map(s => (
              <option key={s} value={s}>{USER_STATUS_LABELS[s] ?? s}</option>
            ))}
          </select>
        </div>

        {/* Research (read-only badge) */}
        <div style={{ padding: "12px 20px", borderRight: "1px solid var(--border)" }}>
          <FieldLabel>Research</FieldLabel>
          {currentResearchStatus === "researched" ? (
            <span style={{ color: "#c084fc", fontFamily: "var(--font-mono)", fontSize: 12, fontWeight: 600 }}>
              Researched
            </span>
          ) : job.is_researching ? (
            <span className="animate-pulse" style={{ color: "var(--amber)", fontSize: 12 }}>⟳ Researching</span>
          ) : (
            <span style={{ color: "var(--text-3)", fontSize: 12 }}>None</span>
          )}
        </div>

{/* Notes */}
        <div style={{ padding: "12px 20px", borderRight: "1px solid var(--border)" }}>
          <FieldLabel>Notes</FieldLabel>
          {editingNote ? (
            <textarea
              value={noteValue}
              onChange={e => setNoteValue(e.target.value)}
              placeholder="Add a note…"
              autoFocus
              className="w-full text-xs outline-none resize-none"
              style={{
                background: "transparent",
                border: "none",
                color: "var(--text-1)",
                fontFamily: "inherit",
                height: 38,
                lineHeight: 1.5,
              }}
            />
          ) : (
            <div
              onClick={() => setEditingNote(true)}
              className="text-xs leading-relaxed cursor-text transition-opacity hover:opacity-80"
              style={{
                color: noteValue ? "var(--text-1)" : "var(--text-3)",
                minHeight: 38,
                paddingTop: 2,
              }}
            >
              {noteValue || <span style={{ fontStyle: "italic" }}>click to add notes…</span>}
            </div>
          )}
        </div>

        {/* Save/cancel for notes */}
        <div style={{ padding: "12px 16px", display: "flex", flexDirection: "column", justifyContent: "flex-end", gap: 4 }}>
          {editingNote ? (
            <>
              <button onClick={saveNote} disabled={saving}
                className="font-data text-xs rounded px-3 py-1 font-medium disabled:opacity-40 transition-colors"
                style={{ background: "var(--green)", color: "#000" }}>
                {saving ? "…" : "Save"}
              </button>
              <button onClick={() => { setEditingNote(false); setNoteValue(data.job?.comment ?? ""); }}
                className="font-data text-xs rounded px-3 py-1 transition-colors"
                style={{ color: "var(--text-2)", border: "1px solid var(--border-hi)" }}>
                Cancel
              </button>
            </>
          ) : (
            <button onClick={() => setEditingNote(true)}
              className="font-data text-xs rounded px-3 py-1 transition-colors"
              style={{ color: "var(--text-3)", border: "1px solid var(--border)" }}>
              Edit
            </button>
          )}
        </div>
      </div>

      {/* ── ZONE 4: Verdict hero ── */}
      <div style={{
        background: verdict.bg,
        borderBottom: `1px solid ${verdict.accent}`,
        padding: "16px 24px",
      }}>
        <div className="flex items-start justify-between gap-6">
          <div className="flex-1 min-w-0">
            <div className="font-data font-bold tracking-widest mb-2"
              style={{ color: verdict.labelColor, fontSize: 11, letterSpacing: "0.15em" }}>
              {verdict.label}
            </div>
            {assessment?.one_line_summary && (
              <p className="text-sm leading-relaxed" style={{ color: "var(--text-1)", maxWidth: 520 }}>
                {assessment.one_line_summary}
              </p>
            )}
          </div>
          <div className="flex items-center gap-4 shrink-0">
            <ScoreBlock label="Relevance" value={assessment?.relevance_score} color="var(--purple)" />
            <ScoreBlock label="Trust" value={research?.trustworthiness_score} color="var(--teal)" />
          </div>
        </div>
      </div>

      {/* ── ZONE 5: Job Description ── */}
      {job.description && (
        <div style={{ padding: "20px 24px", borderBottom: "1px solid var(--border)" }}>
          <SectionLabel>Job Description</SectionLabel>
          <p className="text-sm leading-relaxed whitespace-pre-wrap" style={{ color: "var(--text-2)" }}>
            {job.description.slice(0, 4000)}{job.description.length > 4000 ? "…" : ""}
          </p>
        </div>
      )}

      {/* ── ZONE 7: Role Fit + Company Intel ── */}
      {(assessment || research) && (
        <div style={{ borderBottom: "1px solid var(--border)" }}>
          <div className="grid" style={{ gridTemplateColumns: "1fr 1fr" }}>
            <div style={{ padding: "20px 24px", borderRight: "1px solid var(--border)" }}>
              <SectionLabel>Role Fit</SectionLabel>
              <div className="space-y-2">
                <Row label="Seniority"  value={assessment?.seniority_fit} />
                <Row label="Tech stack" value={assessment?.tech_stack_fit} />
                <Row label="Remote"     value={assessment?.remote_eligibility} />
                <Row label="Salary"     value={assessment?.salary_assessment} />
              </div>
            </div>
            <div style={{ padding: "20px 24px" }}>
              <div className="flex items-center justify-between mb-3">
                <div className="font-data text-xs font-semibold tracking-widest uppercase"
                  style={{ color: "var(--text-3)", letterSpacing: "0.12em" }}>Company</div>
                {currentPipelineStatus === "screened" && currentResearchStatus !== "researched" && !job.is_researching && (
                  <CommandButton jobId={jobId} commands={commands ?? []} onDone={load} compact />
                )}
              </div>
              <div className="space-y-2">
                {research ? (
                  <>
                    <Row label="Legit"      value={research?.legitimacy_check} />
                    <Row label="Entity"     value={research?.hiring_entity_type} />
                    <Row label="Founded"    value={research?.founded_year} />
                    <Row label="HQ"         value={research?.hq_location} />
                    <Row label="Headcount"  value={research?.employee_count} />
                    <Row label="Trend"      value={research?.headcount_trend} />
                    <Row label="Funding"    value={research?.funding_summary} />
                    <Row label="Stage"      value={research?.funding_stage} />
                    <Row label="Glassdoor"  value={research?.glassdoor_summary} />
                    {research?.risk_news && research.risk_news !== "Not found" && (
                      <Row label="Risk"     value={research.risk_news} />
                    )}
                    {research?.research_notes && (
                      <p className="text-xs pt-1 leading-relaxed" style={{ color: "var(--text-2)" }}>
                        {research.research_notes}
                      </p>
                    )}
                  </>
                ) : (
                  <p className="text-xs italic" style={{ color: "var(--text-3)" }}>No research yet</p>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ── ZONE 8: Red Flags ── */}
      {assessment?.red_flag_scan && assessment.red_flag_scan !== "None found" && (
        <div className="flex gap-3 items-start"
          style={{ padding: "14px 24px", background: "var(--amber-bg)", borderBottom: `1px solid var(--amber-border)` }}>
          <span style={{ color: "var(--amber)", fontSize: 14, lineHeight: 1.6 }}>⚠</span>
          <p className="text-xs leading-relaxed" style={{ color: "var(--text-1)" }}>
            {assessment.red_flag_scan}
          </p>
        </div>
      )}

    </div>
  );
}
