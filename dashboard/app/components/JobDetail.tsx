"use client";
import { useEffect, useState } from "react";
import { CommandButton } from "./CommandButton";
import { STATUS_COLORS, PROVIDER_COLORS } from "./JobList";

const STATUSES = ["new","interesting","not_interested","researching","researched","draft_ready","applied","interviewing","rejected","archived"];

const INTERVIEW_STATUSES = ["Not Applied", "Applied", "In process", "Rejected", "Offer", "Landed"];
const INTERVIEW_COLORS: Record<string, { bg: string; color: string }> = {
  "Applied":    { bg: "rgba(96,165,250,0.12)",  color: "var(--blue)" },
  "In process": { bg: "rgba(45,212,191,0.12)",  color: "var(--teal)" },
  "Rejected":   { bg: "rgba(248,113,113,0.12)", color: "var(--red)" },
  "Offer":      { bg: "rgba(34,197,94,0.15)",   color: "var(--green)" },
  "Landed":     { bg: "rgba(167,139,250,0.15)", color: "var(--purple)" },
};

const VERDICT_CONFIG: Record<string, { bg: string; accent: string; label: string; labelColor: string }> = {
  "Apply": {
    bg: "var(--green-bg)",
    accent: "var(--green)",
    label: "APPLY",
    labelColor: "var(--green)",
  },
  "Apply with caution": {
    bg: "var(--amber-bg)",
    accent: "var(--amber)",
    label: "APPLY WITH CAUTION",
    labelColor: "var(--amber)",
  },
  "Skip": {
    bg: "var(--red-bg)",
    accent: "var(--red-border)",
    label: "SKIP",
    labelColor: "var(--text-2)",
  },
};
const DEFAULT_VERDICT = { bg: "var(--surface)", accent: "var(--border-hi)", label: "NOT RESEARCHED", labelColor: "var(--text-3)" };

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
  jobId: number;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  updateJobAction: (id: number, fields: any) => Promise<void>;
  onDelete?: () => void;
}) {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const [data, setData] = useState<any | null>(null);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState({ status: "", comment: "", current_interview_status: "" });
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [applying, setApplying] = useState(false);
  const [interviewStatus, setInterviewStatus] = useState("");

  const load = () => {
    setLoading(true);
    fetch(`/api/jobs/${jobId}`)
      .then(r => r.json())
      .then(d => {
        setData(d);
        setForm({ status: d.job?.status ?? "", comment: d.job?.comment ?? "", current_interview_status: d.job?.current_interview_status ?? "" });
        setInterviewStatus(d.job?.current_interview_status || "Not Applied");
      })
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, [jobId]); // eslint-disable-line react-hooks/exhaustive-deps

  if (loading) return (
    <div className="flex items-center justify-center h-32">
      <span className="font-data text-xs animate-pulse" style={{ color: "var(--text-3)" }}>loading…</span>
    </div>
  );
  if (!data?.job) return <div className="p-6 text-sm" style={{ color: "var(--red)" }}>Job not found</div>;

  const { job, assessment, research, commands } = data;
  const verdict = VERDICT_CONFIG[assessment?.apply_verdict ?? ""] ?? DEFAULT_VERDICT;

  async function save() {
    setSaving(true);
    await updateJobAction(jobId, form);
    setEditing(false);
    setSaving(false);
    load();
  }

  function cancelEdit() {
    setEditing(false);
    setForm({ status: job.status ?? "", comment: job.comment ?? "", current_interview_status: job.current_interview_status ?? "" });
  }

  async function handleDelete() {
    setDeleting(true);
    await fetch(`/api/jobs/${jobId}`, { method: "DELETE" });
    onDelete?.();
  }

  async function handleApply() {
    setApplying(true);
    try {
      await fetch("/api/commands", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ command_type: "apply_job", job_id: jobId }),
      });
      load();
    } finally {
      setApplying(false);
    }
  }

  const canApply = assessment?.apply_verdict === "Apply" || assessment?.apply_verdict === "Apply with caution";

  async function handleInterviewStatus(val: string) {
    setInterviewStatus(val);
    await updateJobAction(jobId, { current_interview_status: val });
  }

  return (
    <div style={{ maxWidth: 820, margin: "0 auto", padding: "0 0 48px 0" }}>

      {/* ── ZONE 1: Verdict Hero ── */}
      <div style={{
        background: verdict.bg,
        borderBottom: `1px solid ${verdict.accent}`,
        padding: "20px 24px",
      }}>
        <div className="flex items-start justify-between gap-6">
          {/* Left: verdict + summary */}
          <div className="flex-1 min-w-0">
            <div className="font-data font-bold tracking-widest mb-2" style={{ color: verdict.labelColor, fontSize: 11, letterSpacing: "0.15em" }}>
              {verdict.label}
            </div>
            {assessment?.one_line_summary && (
              <p className="text-sm leading-relaxed" style={{ color: "var(--text-1)", maxWidth: 520 }}>
                {assessment.one_line_summary}
              </p>
            )}
          </div>

          {/* Right: scores + actions */}
          <div className="flex items-center gap-4 shrink-0">
            <div className="flex gap-4">
              <ScoreBlock label="Relevance" value={assessment?.relevance_score} color="var(--purple)" />
              <ScoreBlock label="Trust" value={research?.trustworthiness_score} color="var(--teal)" />
            </div>

            <div className="flex items-center gap-2" style={{ borderLeft: "1px solid var(--border-hi)", paddingLeft: 16 }}>
              {/* Interview status dropdown */}
              <select
                value={interviewStatus}
                onChange={e => handleInterviewStatus(e.target.value)}
                className="text-xs rounded px-2 py-1.5 outline-none transition-colors"
                style={{
                  background: interviewStatus ? INTERVIEW_COLORS[interviewStatus]?.bg : "var(--surface-hi)",
                  color: interviewStatus ? INTERVIEW_COLORS[interviewStatus]?.color : "var(--text-2)",
                  border: `1px solid ${interviewStatus ? INTERVIEW_COLORS[interviewStatus]?.color + "44" : "var(--border-hi)"}`,
                  fontFamily: "inherit",
                }}
              >
                {INTERVIEW_STATUSES.map(s => (
                  <option key={s} value={s}>{s}</option>
                ))}
              </select>

              <CommandButton jobId={jobId} commands={commands ?? []} onDone={load} compact />
              {canApply && (
                <button onClick={handleApply} disabled={applying}
                  className="text-xs font-medium rounded px-3 py-1.5 transition-colors disabled:opacity-40"
                  style={{ background: "var(--green)", color: "#000" }}>
                  {applying ? "…" : "Apply"}
                </button>
              )}
              {confirmDelete ? (
                <div className="flex items-center gap-1">
                  <span className="text-xs" style={{ color: "var(--text-3)" }}>Delete?</span>
                  <button type="button" onClick={handleDelete} disabled={deleting}
                    className="text-xs rounded px-2 py-1 transition-colors disabled:opacity-40"
                    style={{ background: "var(--red)", color: "#fff" }}>
                    {deleting ? "…" : "Yes"}
                  </button>
                  <button type="button" onClick={() => setConfirmDelete(false)}
                    className="text-xs rounded px-2 py-1 transition-colors"
                    style={{ color: "var(--text-2)", border: "1px solid var(--border-hi)" }}>
                    No
                  </button>
                </div>
              ) : (
                <button type="button" onClick={() => setConfirmDelete(true)} disabled={deleting}
                  className="text-xs rounded px-2 py-1.5 transition-colors disabled:opacity-40"
                  style={{ color: "var(--text-2)", border: "1px solid var(--border-hi)" }}>
                  Delete
                </button>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* ── ZONE 2: Job Title ── */}
      <div style={{ padding: "20px 24px", borderBottom: "1px solid var(--border)" }}>
        <div className="flex items-center gap-2 mb-1">
          <span className="font-data font-bold" style={{ color: "var(--text-1)", fontSize: 15 }}>#{job.id}</span>
          {job.provider && (
            <span className="font-data text-xs px-1.5 py-px rounded"
              style={{
                background: PROVIDER_COLORS[job.provider]?.bg ?? "var(--surface-hi)",
                color: PROVIDER_COLORS[job.provider]?.color ?? "var(--text-3)",
              }}>
              {job.provider}
            </span>
          )}
        </div>
        <h1 className="font-bold leading-tight mb-1" style={{ color: "var(--text-1)", fontSize: 20 }}>
          {job.title ?? "(no title)"}
        </h1>
        <div className="flex items-center gap-2 flex-wrap mb-3">
          <span className="text-sm font-medium" style={{ color: "var(--text-2)" }}>
            {job.posted_company_name}
          </span>
          {job.country && <><span style={{ color: "var(--text-3)" }}>·</span><span className="text-sm" style={{ color: "var(--text-2)" }}>{job.country}</span></>}
          {job.remote_scope && <><span style={{ color: "var(--text-3)" }}>·</span><span className="text-sm" style={{ color: "var(--text-2)" }}>{job.remote_scope}</span></>}
          {(job.salary_range || assessment?.salary_assessment) && (
            <span className="font-data text-xs px-2 py-0.5 rounded"
              style={{ background: "var(--surface-hi)", color: "var(--text-1)", border: "1px solid var(--border-hi)" }}>
              {job.salary_range || assessment?.salary_assessment}
            </span>
          )}
        </div>
        <div className="flex items-center gap-4 flex-wrap">
          {job.date_posted && (
            <span className="font-data text-xs" style={{ color: "var(--text-3)" }}>
              Posted {job.date_posted}
            </span>
          )}
          <span className="font-data text-xs" style={{ color: "var(--text-3)" }}>
            Seen {job.first_seen?.slice(0, 10)}
          </span>
          <a href={job.url} target="_blank" rel="noopener noreferrer"
            className="text-xs font-medium transition-colors"
            style={{ color: "var(--blue)" }}>
            Posting ↗
          </a>
          {job.apply_url && job.apply_url !== job.url && (
            <a href={job.apply_url} target="_blank" rel="noopener noreferrer"
              className="text-xs font-medium"
              style={{ color: "var(--green)" }}>
              Apply ↗
            </a>
          )}
        </div>
      </div>

      {/* ── ZONE 3: Job Description ── */}
      {job.description && (
        <div style={{ padding: "20px 24px", borderBottom: "1px solid var(--border)" }}>
          <SectionLabel>Job Description</SectionLabel>
          <p className="text-sm leading-relaxed whitespace-pre-wrap" style={{ color: "var(--text-2)" }}>
            {job.description.slice(0, 4000)}{job.description.length > 4000 ? "…" : ""}
          </p>
        </div>
      )}

      {/* ── ZONE 4: AI Assessment Notes ── */}
      {(assessment?.assessment_notes || assessment?.ai_native_assessment) && (
        <div style={{ padding: "20px 24px", borderBottom: "1px solid var(--border)" }}>
          <SectionLabel>Assessment</SectionLabel>
          {assessment?.assessment_notes && (
            <p className="text-sm leading-relaxed mb-3" style={{ color: "var(--text-1)" }}>
              {assessment.assessment_notes}
            </p>
          )}
          {assessment?.ai_native_assessment && (
            <div className="flex gap-2 text-xs items-baseline">
              <span className="font-medium shrink-0" style={{ color: "var(--text-3)" }}>AI-native</span>
              <span style={{ color: "var(--text-2)" }}>{assessment.ai_native_assessment}</span>
            </div>
          )}
        </div>
      )}

      {/* ── ZONE 5: Role Fit + Company Intel ── */}
      {(assessment || research) && (
        <div style={{ borderBottom: "1px solid var(--border)" }}>
          <div className="grid" style={{ gridTemplateColumns: "1fr 1fr" }}>

            {/* Role Fit */}
            <div style={{ padding: "20px 24px", borderRight: "1px solid var(--border)" }}>
              <SectionLabel>Role Fit</SectionLabel>
              <div className="space-y-2">
                <Row label="Seniority"  value={assessment?.seniority_fit} />
                <Row label="IC / Mgmt"  value={assessment?.ic_or_management} />
                <Row label="Tech stack" value={assessment?.tech_stack_fit} />
                <Row label="Remote"     value={assessment?.remote_eligibility} />
                <Row label="Salary"     value={assessment?.salary_assessment} />
                <Row label="Visa"       value={assessment?.visa_contract_structure} />
              </div>
            </div>

            {/* Company Intel */}
            <div style={{ padding: "20px 24px" }}>
              <SectionLabel>Company</SectionLabel>
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

      {/* ── ZONE 6: Red Flags ── */}
      {assessment?.red_flag_scan && assessment.red_flag_scan !== "None found" && (
        <div className="flex gap-3 items-start"
          style={{ padding: "14px 24px", background: "var(--amber-bg)", borderBottom: `1px solid var(--amber-border)` }}>
          <span style={{ color: "var(--amber)", fontSize: 14, lineHeight: 1.6 }}>⚠</span>
          <p className="text-xs leading-relaxed" style={{ color: "var(--text-1)" }}>
            {assessment.red_flag_scan}
          </p>
        </div>
      )}

      {/* ── ZONE 7: Workflow ── */}
      <div style={{ padding: "16px 24px" }}>
        <div className="flex items-start gap-4 flex-wrap">
          {/* Status */}
          <div className="flex items-center gap-2">
            {editing ? (
              <select value={form.status} onChange={e => setForm({ ...form, status: e.target.value })}
                className="text-xs rounded px-2 py-1 outline-none"
                style={{ background: "var(--surface-hi)", border: "1px solid var(--border-hi)", color: "var(--text-1)" }}>
                {STATUSES.map(s => <option key={s} value={s}>{s}</option>)}
              </select>
            ) : (
              <span className={`text-xs px-2 py-0.5 rounded ${STATUS_COLORS[job.status] ?? ""}`}>
                {job.status}
              </span>
            )}
          </div>

          {/* Comment */}
          <div className="flex-1 min-w-[200px]">
            {editing ? (
              <textarea value={form.comment} onChange={e => setForm({ ...form, comment: e.target.value })}
                placeholder="Comment…"
                className="w-full text-xs rounded px-2 py-1.5 outline-none resize-none"
                style={{ background: "var(--surface-hi)", border: "1px solid var(--border-hi)", color: "var(--text-1)", height: 56 }} />
            ) : job.comment ? (
              <p className="text-xs leading-relaxed" style={{ color: "var(--text-2)" }}>{job.comment}</p>
            ) : null}
          </div>


          {/* Edit controls */}
          <div className="flex items-center gap-2 ml-auto">
            {!editing ? (
              <button onClick={() => setEditing(true)}
                className="text-xs px-3 py-1.5 rounded transition-colors"
                style={{ color: "var(--text-2)", border: "1px solid var(--border-hi)" }}>
                Edit
              </button>
            ) : (
              <>
                <button onClick={save} disabled={saving}
                  className="text-xs px-3 py-1.5 rounded font-medium transition-colors disabled:opacity-40"
                  style={{ background: "var(--green)", color: "#000" }}>
                  {saving ? "…" : "Save"}
                </button>
                <button onClick={cancelEdit}
                  className="text-xs px-3 py-1.5 rounded transition-colors"
                  style={{ color: "var(--text-2)", border: "1px solid var(--border-hi)" }}>
                  Cancel
                </button>
              </>
            )}
          </div>
        </div>
      </div>

    </div>
  );
}
