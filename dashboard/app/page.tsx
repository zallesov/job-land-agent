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

  return (
    <div className="flex flex-col h-screen bg-gray-950 text-gray-100">
      <header className="flex items-center justify-between px-4 py-2 border-b border-gray-800">
        <h1 className="text-lg font-bold tracking-tight">Job Pipeline</h1>
        <span className="text-sm text-gray-400">{jobs.length} jobs</span>
      </header>
      <div className="flex flex-1 overflow-hidden">
        <JobListClient jobs={jobs} addJobAction={addManualJobAction} />
      </div>
    </div>
  );
}
