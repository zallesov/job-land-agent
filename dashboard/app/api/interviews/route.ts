import { NextResponse } from "next/server";
import { listInterviews, createInterview } from "@/lib/db";
import { unauthorizedResponse } from "@/lib/auth";

export async function GET() {
  const unauth = unauthorizedResponse();
  if (unauth) return unauth;

  return NextResponse.json(await listInterviews());
}

export async function POST() {
  const unauth = unauthorizedResponse();
  if (unauth) return unauth;

  const interview = await createInterview();
  return NextResponse.json(interview, { status: 201 });
}
