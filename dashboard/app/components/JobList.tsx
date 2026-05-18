"use client";
import { useState } from "react";
import { JobDetail } from "./JobDetail";
import { updateJobAction } from "../actions";

const STATUS_COLORS: Record<string, string> = {
  new: "bg-blue-900 text-blue-200",
  interesting: "bg-green-900 text-green-200",
  not_interested: "bg-gray-700 text-gray-400",
  researching: "bg-yellow-900 text-yellow-200",
  researched: "bg-purple-900 text-purple-200",
  draft_ready: "bg-orange-900 text-orange-200",
  applied: "bg-indigo-900 text-indigo-200",
  interviewing: "bg-teal-900 text-teal-200",
  rejected: "bg-red-900 text-red-300",
  archived: "bg-gray-800 text-gray-500",
};

export function JobListClient({
  jobs,
  addJobAction,
}: {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  jobs: any[];
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  addJobAction: (fd: FormData) => Promise<any>;
}) {
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [addUrl, setAddUrl] = useState("");
  const [adding, setAdding] = useState(false);
  const [addError, setAddError] = useState<string | null>(null);

  async function handleAdd(e: React.FormEvent) {
    e.preventDefault();
    setAdding(true);
    setAddError(null);
    try {
      const fd = new FormData();
      fd.set("url", addUrl);
      await addJobAction(fd);
      setAddUrl("");
    } catch (err: unknown) {
      setAddError(err instanceof Error ? err.message : String(err));
    } finally {
      setAdding(false);
    }
  }

  return (
    <>
      <div className="w-[480px] flex flex-col border-r border-gray-800 overflow-hidden shrink-0">
        <form onSubmit={handleAdd} className="flex gap-2 px-3 py-2 border-b border-gray-800">
          <input
            className="flex-1 bg-gray-900 border border-gray-700 rounded px-2 py-1 text-sm"
            placeholder="Add job URL…"
            value={addUrl}
            onChange={(e) => setAddUrl(e.target.value)}
          />
          <button
            type="submit"
            disabled={adding}
            className="bg-blue-700 hover:bg-blue-600 text-white rounded px-3 py-1 text-sm disabled:opacity-50"
          >
            {adding ? "…" : "Add"}
          </button>
        </form>
        {addError && <div className="text-xs text-red-400 px-3 py-1">{addError}</div>}
        <div className="overflow-y-auto flex-1">
          {/* eslint-disable-next-line @typescript-eslint/no-explicit-any */}
          {jobs.map((job: any) => (
            <button
              key={job.id}
              onClick={() => setSelectedId(job.id)}
              className={`w-full text-left px-3 py-2 border-b border-gray-800 hover:bg-gray-900 ${
                selectedId === job.id ? "bg-gray-900 border-l-2 border-l-blue-500" : ""
              }`}
            >
              <div className="flex items-center gap-2 mb-0.5 flex-wrap">
                <span className={`text-xs px-1.5 py-0.5 rounded ${STATUS_COLORS[job.status] ?? "bg-gray-700 text-gray-300"}`}>
                  {job.status}
                </span>
                {job.relevance_score != null && <span className="text-xs text-purple-400">R:{job.relevance_score}</span>}
                {job.trustworthiness_score != null && <span className="text-xs text-teal-400">T:{job.trustworthiness_score}</span>}
                {job.apply_verdict && <span className="text-xs text-yellow-300">{job.apply_verdict}</span>}
                <span className="text-xs text-gray-500 ml-auto">{job.provider}</span>
              </div>
              <div className="font-medium text-sm truncate">{job.title ?? "(no title)"}</div>
              <div className="text-xs text-gray-400 truncate">
                {job.posted_company_name ?? "—"} · {job.country ?? "?"} · {job.remote_scope ?? "?"}
              </div>
              <div className="text-xs text-gray-600">{job.first_seen?.slice(0, 10)}</div>
            </button>
          ))}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-4">
        {selectedId ? (
          <JobDetail jobId={selectedId} key={selectedId} updateJobAction={updateJobAction} />
        ) : (
          <div className="text-gray-600 text-sm mt-8 text-center">Select a job to view details</div>
        )}
      </div>
    </>
  );
}
