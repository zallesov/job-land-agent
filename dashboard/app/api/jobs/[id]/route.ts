import { NextResponse } from "next/server";
import { getJobDetail } from "@/lib/db";

export async function GET(
  _req: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  const jobId = parseInt(id);
  if (isNaN(jobId)) return NextResponse.json({ error: "Bad id" }, { status: 400 });
  const data = getJobDetail(jobId);
  if (!data) return NextResponse.json({ error: "Not found" }, { status: 404 });
  return NextResponse.json(data);
}
