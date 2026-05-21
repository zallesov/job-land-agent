"use client";
import { useState } from "react";

const STATUS_COLOR: Record<string, string> = {
  pending: "text-yellow-400",
  running: "text-blue-400",
  succeeded: "text-green-400",
  failed: "text-red-400",
  cancelled: "text-gray-500",
};

const STATUS_ICON: Record<string, string> = {
  pending: "⟳",
  running: "⟳",
  succeeded: "✓",
  failed: "✕",
  cancelled: "–",
};

export function CommandButton({ jobId, commands, onDone, compact = false }: {
  jobId: number;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  commands: any[];
  onDone?: () => void;
  compact?: boolean;
}) {
  const [triggering, setTriggering] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const latest = commands[0] ?? null;
  const canTrigger = !latest || !["pending", "running"].includes(latest.status);

  async function triggerResearch() {
    setTriggering(true);
    setError(null);
    try {
      const res = await fetch("/api/commands", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ command_type: "research_job", job_id: jobId }),
      });
      if (!res.ok) throw new Error(await res.text());
      onDone?.();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setTriggering(false);
    }
  }

  if (compact) {
    return (
      <div className="flex items-center gap-1.5">
        {latest && (
          <span className={`text-xs ${STATUS_COLOR[latest.status] ?? "text-gray-400"}`}>
            {STATUS_ICON[latest.status] ?? "?"}
          </span>
        )}
        <button
          onClick={triggerResearch}
          disabled={triggering || !canTrigger}
          className="text-xs bg-purple-800 hover:bg-purple-700 disabled:opacity-40 rounded px-2 py-1"
        >
          {triggering ? "Queuing…" : "Research"}
        </button>
        {error && <span className="text-xs text-red-400">{error}</span>}
      </div>
    );
  }

  return (
    <div className="bg-gray-900 rounded p-3 space-y-2">
      <div className="font-semibold text-sm">Research</div>
      {latest && (
        <div className="text-xs space-y-0.5">
          <span className={STATUS_COLOR[latest.status] ?? "text-gray-400"}>{latest.status}</span>
          {latest.finished_at && <span className="text-gray-500 ml-2">{latest.finished_at.slice(0, 16)}</span>}
          {latest.result_json && (() => {
            try {
              const r = JSON.parse(latest.result_json);
              return <div className="text-green-400">{r.apply_verdict} · R:{r.relevance_score} · T:{r.trustworthiness_score}</div>;
            } catch { return null; }
          })()}
          {latest.error && <div className="text-red-400">{latest.error}</div>}
        </div>
      )}
      <button onClick={triggerResearch} disabled={triggering || !canTrigger}
        className="bg-purple-700 hover:bg-purple-600 disabled:opacity-40 rounded px-3 py-1 text-sm">
        {triggering ? "Queuing…" : "Research job"}
      </button>
      {error && <div className="text-xs text-red-400">{error}</div>}
    </div>
  );
}
