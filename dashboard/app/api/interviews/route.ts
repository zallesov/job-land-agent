import { NextResponse } from "next/server";
import { listInterviews, createInterview } from "@/lib/db";

export async function GET() {
  return NextResponse.json(await listInterviews());
}

export async function POST() {
  const interview = await createInterview();
  return NextResponse.json(interview, { status: 201 });
}
