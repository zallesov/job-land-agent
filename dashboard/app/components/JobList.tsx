"use client";
import { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import PocketBase from "pocketbase";
import { JobDetail } from "./JobDetail";
import { updateJobAction } from "../actions";
import { Logo } from "./Logo";
import { PB_URL } from "@/lib/pb";

export const PIPELINE_STATUS_COLORS: Record<string, string> = {
  new:            "bg-blue-900/60 text-blue-300",
  enriched:       "bg-sky-900/60 text-sky-300",
  screened:       "bg-emerald-900/60 text-emerald-300",
  enrich_failed:  "bg-red-900/20 text-red-600",
  screen_failed:  "bg-orange-900/20 text-orange-600",
};

export const USER_STATUS_COLORS: Record<string, string> = {
  interesting:     "bg-green-900/60 text-green-300",
  not_interesting: "bg-white/5 text-[var(--text-3)]",
  applied:         "bg-indigo-900/60 text-indigo-300",
  rejected:        "bg-red-900/40 text-red-400",
  interviewing:    "bg-teal-900/60 text-teal-200",
  offer:           "bg-purple-900/60 text-purple-300",
};


const VERDICT_LEFT: Record<string, string> = {
  "Strong Apply":       "border-l-[var(--green)]",
  "Apply with Caution": "border-l-[var(--amber)]",
  "Need Research":      "border-l-[#60a5fa]",
  "Skip":               "border-l-[var(--red-border)]",
};

const VERDICT_LABEL: Record<string, string> = {
  "Strong Apply":       "text-[var(--green)]",
  "Apply with Caution": "text-[var(--amber)]",
  "Need Research":      "text-[#60a5fa]",
  "Skip":               "text-[var(--text-3)]",
};

export const PROVIDER_COLORS: Record<string, { bg: string; color: string }> = {
  greenhouse: { bg: "rgba(34,197,94,0.13)",   color: "#4ade80" },
  jobleads:   { bg: "rgba(251,146,60,0.13)",  color: "#fb923c" },
  wellfound:  { bg: "rgba(167,139,250,0.13)", color: "#a78bfa" },
  sprout:     { bg: "rgba(45,212,191,0.13)",  color: "#2dd4bf" },
  hirify:     { bg: "rgba(56,189,248,0.13)",  color: "#38bdf8" },
};

const USER_STATUS_PRIORITY: Record<string, number> = {
  offer:           0,
  interviewing:    1,
  applied:         2,
  interesting:     3,
  not_interesting: 8,
  rejected:        9,
};

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function sortJobs(jobs: any[], sortBy: "newest" | "score" | "status"): any[] {
  const arr = [...jobs];
  if (sortBy === "newest") return arr.sort((a, b) => b.id.localeCompare(a.id));
  if (sortBy === "score") {
    return arr.sort((a, b) => {
      const as_ = (a.relevance_score ?? -1) + (a.trustworthiness_score ?? -1);
      const bs_ = (b.relevance_score ?? -1) + (b.trustworthiness_score ?? -1);
      return as_ !== bs_ ? bs_ - as_ : b.id.localeCompare(a.id);
    });
  }
  return arr.sort((a, b) => {
    const ap = USER_STATUS_PRIORITY[a.user_status] ?? 5;
    const bp = USER_STATUS_PRIORITY[b.user_status] ?? 5;
    if (ap !== bp) return ap - bp;
    const as_ = (a.relevance_score ?? -1) + (a.trustworthiness_score ?? -1);
    const bs_ = (b.relevance_score ?? -1) + (b.trustworthiness_score ?? -1);
    return bs_ - as_;
  });
}

export function JobListClient({
  jobs: initialJobs, addJobAction, initialJobId,
}: {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  jobs: any[];
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  addJobAction: (fd: FormData) => Promise<any>;
  initialJobId?: string | null;
}) {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const [jobs, setJobs] = useState<any[]>(initialJobs);
  const [selectedId, setSelectedId] = useState<string | null>(initialJobId ?? null);
  const [deletedIds, setDeletedIds] = useState<Set<string>>(new Set());
  const [addUrl, setAddUrl] = useState("");
  const [adding, setAdding] = useState(false);
  const [addError, setAddError] = useState<string | null>(null);
  const [sortBy, setSortBy] = useState<"newest" | "score" | "status">("score");
  const [verdictFilter, setVerdictFilter] = useState<string | null>(null);
  const router = useRouter();
  const pbRef = useRef<PocketBase | null>(null);

  // Realtime subscriptions — replace the old polling
  useEffect(() => {
    const pb = new PocketBase(PB_URL);
    pbRef.current = pb;

    pb.collection('jobs').subscribe('*', (e) => {
      if (e.action === 'update') {
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        setJobs(prev => prev.map((j: any) => j.id === e.record.id ? { ...j, ...e.record } : j));
      } else if (e.action === 'create') {
        setJobs(prev => [e.record, ...prev]);
      } else if (e.action === 'delete') {
        setJobs(prev => prev.filter((j: any) => j.id !== e.record.id)); // eslint-disable-line @typescript-eslint/no-explicit-any
      }
    }).catch(() => { /* realtime unavailable — silent */ });

    pb.collection('job_assessments').subscribe('*', (e) => {
      if (e.action === 'create' || e.action === 'update') {
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        setJobs(prev => prev.map((j: any) => j.id === e.record['job_id']
          ? { ...j, relevance_score: e.record['relevance_score'], apply_verdict: e.record['apply_verdict'] }
          : j));
      }
    }).catch(() => { /* silent */ });

    pb.collection('agent_commands').subscribe('*', (e) => {
      if (e.action === 'update' || e.action === 'create') {
        const payload = e.record['payload_json'];
        const p = typeof payload === 'string' ? (() => { try { return JSON.parse(payload); } catch { return null; } })() : payload;
        if (!p?.job_id) return;
        const jid = String(p.job_id).padStart(15, '0');
        const status = e.record['status'] as string;
        const active = status === 'pending' || status === 'running';
        const type = e.record['command_type'] as string;
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        setJobs(prev => prev.map((j: any) => {
          if (j.id !== jid) return j;
          return {
            ...j,
            is_researching: type === 'research_job' ? (active ? 1 : 0) : j.is_researching,
            is_scraping:    type === 'scrape_job'   ? (active ? 1 : 0) : j.is_scraping,
          };
        }));
      }
    }).catch(() => { /* silent */ });

    return () => {
      pb.collection('jobs').unsubscribe('*').catch(() => {});
      pb.collection('job_assessments').unsubscribe('*').catch(() => {});
      pb.collection('agent_commands').unsubscribe('*').catch(() => {});
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  function selectJob(id: string) {
    setSelectedId(id);
    router.replace(`?job=${id}`, { scroll: false });
  }

  async function handleAdd(e: React.FormEvent) {
    e.preventDefault();
    setAdding(true);
    setAddError(null);
    try {
      const fd = new FormData();
      fd.set("url", addUrl);
      const result = await addJobAction(fd);
      setAddUrl("");
      if (result?.id) selectJob(result.id);
    } catch (err: unknown) {
      setAddError(err instanceof Error ? err.message : String(err));
    } finally {
      setAdding(false);
    }
  }

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const visibleJobs = sortJobs(
    jobs.filter((job: any) => { // eslint-disable-line @typescript-eslint/no-explicit-any
      if (deletedIds.has(job.id)) return false;
      if (verdictFilter === "_applied") return job.user_status === "applied";
      if (verdictFilter && job.apply_verdict !== verdictFilter) return false;
      return true;
    }),
    sortBy,
  );

  return (
    <>
      {/* LEFT PANEL */}
      <div
        className="flex flex-col shrink-0 overflow-hidden"
        style={{ width: 490, borderRight: "1px solid var(--border)" }}
      >
        {/* Header */}
        <div style={{ borderBottom: "1px solid var(--border)", padding: "10px 12px" }}
          className="flex items-center justify-between">
          <Logo iconSize={20} />
          <span className="font-data text-xs" style={{ color: "var(--text-3)" }}>
            {visibleJobs.length}/{jobs.length}
          </span>
        </div>

        {/* Add URL */}
        <form onSubmit={handleAdd} className="flex gap-2 px-3 py-2"
          style={{ borderBottom: "1px solid var(--border)" }}>
          <input
            className="flex-1 rounded px-2 py-1.5 text-xs outline-none transition-colors"
            style={{
              background: "var(--surface-hi)", border: "1px solid var(--border-hi)",
              color: "var(--text-1)",
            }}
            placeholder="Paste job URL to add…"
            value={addUrl}
            onChange={(e) => setAddUrl(e.target.value)}
          />
          <button
            type="submit" disabled={adding}
            className="rounded px-3 py-1.5 text-xs font-medium transition-colors disabled:opacity-40"
            style={{ background: "var(--blue)", color: "#000" }}
          >
            {adding ? "…" : "Add"}
          </button>
        </form>
        {addError && <div className="text-xs px-3 py-1" style={{ color: "var(--red)" }}>{addError}</div>}

        {/* Sort + filter bar */}
        <div className="flex items-center gap-1 px-3 py-1.5"
          style={{ borderBottom: "1px solid var(--border)", background: "var(--surface)" }}>
          {(["score", "status", "newest"] as const).map((opt) => (
            <button key={opt} onClick={() => setSortBy(opt)}
              className="text-xs px-2 py-0.5 rounded transition-colors"
              style={sortBy === opt
                ? { background: "var(--surface-hi)", color: "var(--text-1)", border: "1px solid var(--border-hi)" }
                : { color: "var(--text-2)", border: "1px solid transparent" }
              }
            >
              {opt === "score" ? "Score" : opt === "status" ? "Status" : "New"}
            </button>
          ))}
          <div style={{ width: 1, height: 12, background: "var(--border-hi)", margin: "0 4px" }} />
          {([
            { label: "All",      value: null },
            { label: "Apply",    value: "Strong Apply" },
            { label: "Caution",  value: "Apply with Caution" },
            { label: "Research", value: "Need Research" },
            { label: "Applied",  value: "_applied" },
          ] as const).map(({ label, value }) => (
            <button key={label} onClick={() => setVerdictFilter(value)}
              className="text-xs px-2 py-0.5 rounded transition-colors"
              style={verdictFilter === value
                ? { background: "var(--surface-hi)", color: "var(--text-1)", border: "1px solid var(--border-hi)" }
                : { color: "var(--text-2)", border: "1px solid transparent" }
              }
            >
              {label}
            </button>
          ))}
        </div>

        {/* Job list */}
        <div className="overflow-y-auto flex-1">
          {/* eslint-disable-next-line @typescript-eslint/no-explicit-any */}
          {visibleJobs.map((job: any) => {
            const isSelected = selectedId === job.id;
            const isApplied = job.user_status === "applied";
            const verdictBorder = isApplied ? "border-l-[#4ade80]" : (VERDICT_LEFT[job.apply_verdict ?? ""] ?? "border-l-transparent");
            const verdictColor = VERDICT_LABEL[job.apply_verdict ?? ""] ?? "";
            const rowBg = isSelected
              ? (isApplied ? "rgba(34,197,94,0.12)" : "var(--surface-hi)")
              : (isApplied ? "rgba(34,197,94,0.05)" : "transparent");
            const rowHoverBg = isApplied ? "rgba(34,197,94,0.09)" : "var(--surface)";
            return (
              <button
                key={job.id}
                onClick={() => selectJob(job.id)}
                className={`w-full text-left px-3 py-2.5 border-l-2 transition-colors ${verdictBorder}`}
                style={{
                  borderBottom: "1px solid var(--border)",
                  background: rowBg,
                }}
                onMouseEnter={e => { if (!isSelected) (e.currentTarget as HTMLElement).style.background = rowHoverBg; }}
                onMouseLeave={e => { if (!isSelected) (e.currentTarget as HTMLElement).style.background = isApplied ? "rgba(34,197,94,0.05)" : "transparent"; }}
              >
                {/* Title */}
                <div className="text-sm font-semibold truncate leading-tight mb-0.5"
                  style={{ color: "var(--text-1)" }}>
                  <span className="font-data font-bold mr-1.5" style={{ color: "var(--text-2)", fontSize: 12 }}>
                    #{parseInt(job.id) || job.id}
                  </span>
                  {job.title ?? "(no title)"}
                </div>

                {/* Company + location + source */}
                <div className="flex items-center gap-1.5 text-xs truncate mb-2" style={{ color: "var(--text-2)" }}>
                  {job.posted_company_name ?? "—"}
                  {job.country ? ` · ${job.country}` : ""}
                  {job.remote_scope ? ` · ${job.remote_scope}` : ""}
                  {job.provider && (
                    <span className="font-data shrink-0 px-1 py-px rounded"
                      style={{
                        background: PROVIDER_COLORS[job.provider]?.bg ?? "var(--surface-hi)",
                        color: PROVIDER_COLORS[job.provider]?.color ?? "var(--text-3)",
                        fontSize: 10,
                      }}>
                      {job.provider}
                    </span>
                  )}
                </div>

                {/* Bottom row: verdict + scores + status */}
                <div className="flex items-center gap-2">
                  {job.is_scraping ? (
                    <span className="text-xs animate-pulse" style={{ color: "var(--blue)" }}>⟳ scraping</span>
                  ) : job.apply_verdict ? (
                    <span className={`text-xs font-data font-medium ${verdictColor}`}>
                      {job.apply_verdict === "Apply with caution" ? "Caution" : job.apply_verdict}
                    </span>
                  ) : null}

                  {job.relevance_score != null && (
                    <span className="font-data text-xs" style={{ color: "var(--purple)" }}>R:{job.relevance_score}</span>
                  )}
                  {job.trustworthiness_score != null && (
                    <span className="font-data text-xs" style={{ color: "var(--teal)" }}>T:{job.trustworthiness_score}</span>
                  )}

{/* Pipeline status badge */}
                  <span className={`ml-auto text-[10px] px-1.5 py-px rounded font-medium ${PIPELINE_STATUS_COLORS[job.pipeline_status] ?? "bg-white/5 text-[var(--text-3)]"}`}>
                    {job.pipeline_status ?? "—"}
                  </span>

                  {/* User status badge — only if set */}
                  {job.user_status && (
                    <span className={`text-[10px] px-1.5 py-px rounded font-medium ${USER_STATUS_COLORS[job.user_status] ?? ""}`}>
                      {job.user_status.replace(/_/g, " ")}
                    </span>
                  )}

                  {/* Research badge — only if researched */}
                  {job.research_status === "researched" && (
                    <span className="text-[10px] px-1.5 py-px rounded font-medium bg-purple-900/40 text-purple-300">
                      researched
                    </span>
                  )}
                </div>
              </button>
            );
          })}
        </div>
      </div>

      {/* RIGHT PANEL */}
      <div className="flex-1 overflow-y-auto" style={{ background: "var(--bg)" }}>
        {selectedId ? (
          <JobDetail
            jobId={selectedId}
            key={selectedId}
            updateJobAction={updateJobAction}
            onDelete={() => {
              setDeletedIds(prev => { const s = new Set(prev); s.add(selectedId); return s; });
              setSelectedId(null);
            }}
          />
        ) : (
          <div className="flex items-center justify-center h-full">
            <p className="text-sm" style={{ color: "var(--text-3)" }}>Select a job to view details</p>
          </div>
        )}
      </div>
    </>
  );
}
