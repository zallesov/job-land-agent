import { listJobs, type JobFilters } from "@/lib/db";
import { JobListClient } from "./components/JobList";
import { addManualJobAction } from "./actions";

export default async function DashboardPage({
  searchParams,
}: {
  searchParams: Promise<{ [key: string]: string | undefined }>;
}) {
  const params = await searchParams;
  const filters: JobFilters = {
    status: params.status,
    provider: params.provider,
    country: params.country,
    remote_scope: params.remote_scope,
    unresearched: params.unresearched === "1",
    new_only: params.new_only === "1",
  };
  const jobs = listJobs(filters);
  const initialJobId = params.job ? parseInt(params.job, 10) || null : null;

  return (
    <div className="flex h-screen" style={{ background: "var(--bg)", color: "var(--text-1)" }}>
      <JobListClient jobs={jobs} addJobAction={addManualJobAction} initialJobId={initialJobId} />
    </div>
  );
}
