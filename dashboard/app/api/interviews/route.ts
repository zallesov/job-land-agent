import { NextResponse } from "next/server";
import { listInterviews, createInterview } from "@/lib/db";

export async function GET() {
  return NextResponse.json(listInterviews());
}

export async function POST() {
  const interview = createInterview();
  return NextResponse.json(interview, { status: 201 });
}
