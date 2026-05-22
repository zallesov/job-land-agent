"use client";
import { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { JobDetail } from "./JobDetail";
import { updateJobAction } from "../actions";
import { Logo } from "./Logo";

export const STATUS_COLORS: Record<string, string> = {
  new:            "bg-blue-900/60 text-blue-300",
  interesting:    "bg-green-900/60 text-green-300",
  not_interested: "bg-white/5 text-[var(--text-3)]",
  researching:    "bg-yellow-900/60 text-yellow-300",
  researched:     "bg-purple-900/60 text-purple-300",
  draft_ready:    "bg-orange-900/60 text-orange-300",
  applied:        "bg-indigo-900/60 text-indigo-300",
  interviewing:   "bg-teal-900/60 text-teal-200",
  rejected:       "bg-red-900/40 text-red-400",
  archived:       "bg-white/5 text-[var(--text-3)]",
  listed:         "bg-slate-900/60 text-slate-400",
  enrich_failed:  "bg-red-900/20 text-red-600",
  sanity_failed:  "bg-orange-900/20 text-orange-600",
};

const INTERVIEW_PILL: Record<string, { bg: string; color: string }> = {
  "Applied":    { bg: "rgba(96,165,250,0.12)",  color: "#60a5fa" },
  "In process": { bg: "rgba(45,212,191,0.12)",  color: "#2dd4bf" },
  "Rejected":   { bg: "rgba(248,113,113,0.12)", color: "#f87171" },
  "Offer":      { bg: "rgba(34,197,94,0.15)",   color: "#22c55e" },
  "Landed":     { bg: "rgba(167,139,250,0.15)", color: "#a78bfa" },
};

const VERDICT_LEFT: Record<string, string> = {
  "Apply":              "border-l-[var(--green)]",
  "Apply with caution": "border-l-[var(--amber)]",
  "Skip":               "border-l-[var(--red-border)]",
};

const VERDICT_LABEL: Record<string, string> = {
  "Apply":              "text-[var(--green)]",
  "Apply with caution": "text-[var(--amber)]",
  "Skip":               "text-[var(--text-3)]",
};

export const PROVIDER_COLORS: Record<string, { bg: string; color: string }> = {
  greenhouse: { bg: "rgba(34,197,94,0.13)",   color: "#4ade80" },
  jobleads:   { bg: "rgba(251,146,60,0.13)",  color: "#fb923c" },
  wellfound:  { bg: "rgba(167,139,250,0.13)", color: "#a78bfa" },
  sprout:     { bg: "rgba(45,212,191,0.13)",  color: "#2dd4bf" },
  hirify:     { bg: "rgba(56,189,248,0.13)",  color: "#38bdf8" },
};

const STATUS_PRIORITY: Record<string, number> = {
  interviewing: 0, applied: 1, draft_ready: 2, interesting: 3,
  researched: 4, new: 5, listed: 5.5, researching: 6, not_interested: 7, rejected: 8, archived: 9,
  enrich_failed: 10, sanity_failed: 11,
};

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function sortJobs(jobs: any[], sortBy: "newest" | "score" | "status"): any[] {
  const arr = [...jobs];
  if (sortBy === "newest") return arr.sort((a, b) => b.id - a.id);
  if (sortBy === "score") {
    return arr.sort((a, b) => {
      const as_ = (a.relevance_score ?? -1) + (a.trustworthiness_score ?? -1);
      const bs_ = (b.relevance_score ?? -1) + (b.trustworthiness_score ?? -1);
      return as_ !== bs_ ? bs_ - as_ : b.id - a.id;
    });
  }
  return arr.sort((a, b) => {
    const ap = STATUS_PRIORITY[a.status] ?? 99;
    const bp = STATUS_PRIORITY[b.status] ?? 99;
    if (ap !== bp) return ap - bp;
    const as_ = (a.relevance_score ?? -1) + (a.trustworthiness_score ?? -1);
    const bs_ = (b.relevance_score ?? -1) + (b.trustworthiness_score ?? -1);
    return bs_ - as_;
  });
}

export function JobListClient({
  jobs, addJobAction, initialJobId,
}: {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  jobs: any[];
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  addJobAction: (fd: FormData) => Promise<any>;
  initialJobId?: number | null;
}) {
  const [selectedId, setSelectedId] = useState<number | null>(initialJobId ?? null);
  const [deletedIds, setDeletedIds] = useState<Set<number>>(new Set());
  const [addUrl, setAddUrl] = useState("");
  const [adding, setAdding] = useState(false);
  const [addError, setAddError] = useState<string | null>(null);
  const [sortBy, setSortBy] = useState<"newest" | "score" | "status">("score");
  const [applyOnly, setApplyOnly] = useState(false);
  const router = useRouter();
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const hasActive = jobs.some((j: any) => j.is_researching || j.is_scraping);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (hasActive) pollRef.current = setInterval(() => router.refresh(), 5000);
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, [hasActive, router]);

  function selectJob(id: number) {
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
      if (applyOnly && job.apply_verdict !== "Apply" && job.apply_verdict !== "Apply with caution") return false;
      return true;
    }),
    sortBy,
  );

  return (
    <>
      {/* LEFT PANEL */}
      <div
        className="flex flex-col shrink-0 overflow-hidden"
        style={{ width: 380, borderRight: "1px solid var(--border)" }}
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
          <button onClick={() => setApplyOnly(v => !v)}
            className="text-xs px-2 py-0.5 rounded transition-colors"
            style={applyOnly
              ? { background: "var(--green-bg)", color: "var(--green)", border: "1px solid var(--green-border)" }
              : { color: "var(--text-2)", border: "1px solid transparent" }
            }
          >
            Apply only
          </button>
        </div>

        {/* Job list */}
        <div className="overflow-y-auto flex-1">
          {/* eslint-disable-next-line @typescript-eslint/no-explicit-any */}
          {visibleJobs.map((job: any) => {
            const isSelected = selectedId === job.id;
            const verdictBorder = VERDICT_LEFT[job.apply_verdict ?? ""] ?? "border-l-transparent";
            const verdictColor = VERDICT_LABEL[job.apply_verdict ?? ""] ?? "";
            return (
              <button
                key={job.id}
                onClick={() => selectJob(job.id)}
                className={`w-full text-left px-3 py-2.5 border-l-2 transition-colors ${verdictBorder}`}
                style={{
                  borderBottom: "1px solid var(--border)",
                  background: isSelected ? "var(--surface-hi)" : "transparent",
                }}
                onMouseEnter={e => { if (!isSelected) (e.currentTarget as HTMLElement).style.background = "var(--surface)"; }}
                onMouseLeave={e => { if (!isSelected) (e.currentTarget as HTMLElement).style.background = "transparent"; }}
              >
                {/* Title */}
                <div className="text-sm font-semibold truncate leading-tight mb-0.5"
                  style={{ color: "var(--text-1)" }}>
                  <span className="font-data font-bold mr-1.5" style={{ color: "var(--text-2)", fontSize: 12 }}>
                    #{job.id}
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
                  ) : job.is_researching ? (
                    <span className="text-xs animate-pulse" style={{ color: "var(--amber)" }}>⟳ researching</span>
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

                  {job.current_interview_status && job.current_interview_status !== "Not Applied" && INTERVIEW_PILL[job.current_interview_status] && (
                    <span className="font-data text-xs px-1.5 py-px rounded font-medium"
                      style={{
                        background: INTERVIEW_PILL[job.current_interview_status].bg,
                        color: INTERVIEW_PILL[job.current_interview_status].color,
                        fontSize: 10,
                      }}>
                      {job.current_interview_status}
                    </span>
                  )}
                  <span className="ml-auto text-xs px-1.5 py-px rounded"
                    style={{
                      background: "var(--surface-hi)",
                      color: "var(--text-2)",
                      border: "1px solid var(--border-hi)",
                      fontSize: 10,
                    }}>
                    {job.status}
                  </span>
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
              setDeletedIds(prev => new Set(prev).add(selectedId));
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
