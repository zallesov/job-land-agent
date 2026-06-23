import { Suspense } from "react";
import { JobListClient } from "./components/JobList";
import { addManualJobAction } from "./actions";

// Jobs are fetched client-side (via /api/jobs) and kept live via PocketBase
// realtime subscriptions — nothing dynamic is rendered server-side, so there
// is no server/client markup to keep in sync (no SSR hydration mismatches).
export default async function DashboardPage({
  searchParams,
}: {
  searchParams: Promise<{ [key: string]: string | undefined }>;
}) {
  const params = await searchParams;
  const initialJobId = params.job ?? null;

  return (
    <div className="flex" style={{ height: "calc(100vh - 2.5rem)", background: "var(--bg)", color: "var(--text-1)" }}>
      <Suspense fallback={null}>
        <JobListClient addJobAction={addManualJobAction} initialJobId={initialJobId} />
      </Suspense>
    </div>
  );
}
