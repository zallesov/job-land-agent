"use client";
import { useEffect, useState } from "react";
import { CommandButton } from "./CommandButton";

const STATUSES = ["new","interesting","not_interested","researching","researched","draft_ready","applied","interviewing","rejected","archived"];

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

  const load = () => {
    setLoading(true);
    fetch(`/api/jobs/${jobId}`)
      .then((r) => r.json())
      .then((d) => {
        setData(d);
        setForm({ status: d.job?.status ?? "", comment: d.job?.comment ?? "", current_interview_status: d.job?.current_interview_status ?? "" });
      })
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, [jobId]); // eslint-disable-line react-hooks/exhaustive-deps

  if (loading) return <div className="text-gray-500 text-sm">Loading…</div>;
  if (!data?.job) return <div className="text-red-400 text-sm">Job not found</div>;

  const { job, assessment, research, commands } = data;

  async function save() {
    setSaving(true);
    await updateJobAction(jobId, form);
    setEditing(false);
    setSaving(false);
    load();
  }

  async function handleDelete() {
    if (!confirm("Soft-delete this job? It won't appear again even if re-scraped.")) return;
    setDeleting(true);
    await fetch(`/api/jobs/${jobId}`, { method: "DELETE" });
    onDelete?.();
  }

  return (
    <div className="space-y-4 max-w-2xl">
      <div>
        <div className="flex items-start justify-between gap-2">
          <h2 className="text-xl font-bold">{job.title ?? "(no title)"}</h2>
          <button
            onClick={handleDelete}
            disabled={deleting}
            className="text-xs text-red-500 hover:text-red-400 border border-red-800 hover:border-red-600 rounded px-2 py-1 shrink-0 disabled:opacity-50"
          >
            {deleting ? "Deleting…" : "Delete"}
          </button>
        </div>
        <p className="text-gray-400 text-sm">{job.posted_company_name} · {job.country} · {job.remote_scope}</p>
        <div className="flex gap-3 mt-1 text-xs text-gray-500 flex-wrap">
          <span>First seen: {job.first_seen?.slice(0, 10)}</span>
          <span>Last seen: {job.last_seen?.slice(0, 10)}</span>
          <span>Provider: {job.provider}</span>
          {job.apply_url && <a href={job.apply_url} target="_blank" rel="noopener noreferrer" className="text-blue-400 underline">Apply</a>}
        </div>
      </div>

      {assessment && (
        <div className="bg-gray-900 rounded p-3 space-y-1">
          <div className="font-semibold text-sm text-purple-300">Assessment</div>
          <div className="text-sm">Verdict: <span className="font-medium">{assessment.apply_verdict}</span>
            {assessment.relevance_score != null && <span className="ml-2 text-purple-400">R:{assessment.relevance_score}</span>}
          </div>
          {assessment.one_line_summary && <div className="text-sm text-gray-300">{assessment.one_line_summary}</div>}
          {assessment.red_flag_scan && <div className="text-xs text-red-400">&#9888; {assessment.red_flag_scan}</div>}
          {assessment.seniority_fit && <div className="text-xs text-gray-400">Seniority: {assessment.seniority_fit}</div>}
          {assessment.tech_stack_fit && <div className="text-xs text-gray-400">Tech: {assessment.tech_stack_fit}</div>}
          {assessment.salary_assessment && <div className="text-xs text-gray-400">Salary: {assessment.salary_assessment}</div>}
          {assessment.remote_eligibility && <div className="text-xs text-gray-400">Remote: {assessment.remote_eligibility}</div>}
        </div>
      )}

      {research && (
        <div className="bg-gray-900 rounded p-3 space-y-1">
          <div className="font-semibold text-sm text-teal-300">Company Research</div>
          {research.trustworthiness_score != null && <div className="text-sm">Trust: <span className="font-medium">{research.trustworthiness_score}</span></div>}
          {research.hiring_entity_type && <div className="text-xs text-yellow-400">{research.hiring_entity_type}</div>}
          {research.glassdoor_summary && <div className="text-xs text-gray-400">Glassdoor: {research.glassdoor_summary}</div>}
          {research.funding_summary && <div className="text-xs text-gray-400">Funding: {research.funding_summary}</div>}
          {research.research_notes && <div className="text-xs text-gray-400">{research.research_notes}</div>}
          {research.researched_at && <div className="text-xs text-gray-600">Researched: {research.researched_at?.slice(0,10)}</div>}
        </div>
      )}

      <div className="bg-gray-900 rounded p-3">
        <div className="font-semibold text-sm mb-2">Workflow</div>
        {editing ? (
          <div className="space-y-2">
            <select value={form.status} onChange={(e) => setForm({ ...form, status: e.target.value })}
              className="bg-gray-800 border border-gray-600 rounded px-2 py-1 text-sm w-full">
              {STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
            <textarea value={form.comment} onChange={(e) => setForm({ ...form, comment: e.target.value })}
              placeholder="Comment…" className="bg-gray-800 border border-gray-600 rounded px-2 py-1 text-sm w-full h-16 resize-none" />
            <input value={form.current_interview_status} onChange={(e) => setForm({ ...form, current_interview_status: e.target.value })}
              placeholder="Interview status…" className="bg-gray-800 border border-gray-600 rounded px-2 py-1 text-sm w-full" />
            <div className="flex gap-2">
              <button onClick={save} disabled={saving} className="bg-green-700 hover:bg-green-600 rounded px-3 py-1 text-sm disabled:opacity-50">{saving ? "Saving…" : "Save"}</button>
              <button onClick={() => setEditing(false)} className="bg-gray-700 hover:bg-gray-600 rounded px-3 py-1 text-sm">Cancel</button>
            </div>
          </div>
        ) : (
          <div className="space-y-1">
            <div className="text-sm">Status: <span className="font-medium">{job.status}</span></div>
            {job.comment && <div className="text-sm text-gray-400">{job.comment}</div>}
            {job.current_interview_status && <div className="text-xs text-gray-500">{job.current_interview_status}</div>}
            <button onClick={() => setEditing(true)} className="text-xs text-blue-400 underline mt-1">Edit</button>
          </div>
        )}
      </div>

      <CommandButton jobId={jobId} commands={commands ?? []} onDone={load} />

      {job.description && (
        <details className="bg-gray-900 rounded p-3">
          <summary className="text-sm font-semibold cursor-pointer select-none">Description</summary>
          <p className="text-xs text-gray-400 mt-2 whitespace-pre-wrap leading-relaxed">
            {job.description.slice(0, 3000)}{job.description.length > 3000 && "…"}
          </p>
        </details>
      )}
    </div>
  );
}
