import { NextRequest, NextResponse } from "next/server";
import { listJobs, type JobFilters } from "@/lib/db";
import { unauthorizedResponse } from "@/lib/auth";

export async function GET(req: NextRequest) {
  const unauth = unauthorizedResponse();
  if (unauth) return unauth;

  const sp = req.nextUrl.searchParams;
  const filters: JobFilters = {
    status: sp.get("status") ?? undefined,
    provider: sp.get("provider") ?? undefined,
    country: sp.get("country") ?? undefined,
    remote_scope: sp.get("remote_scope") ?? undefined,
    unresearched: sp.get("unresearched") === "1",
    new_only: sp.get("new_only") === "1",
  };
  return NextResponse.json(await listJobs(filters));
}
