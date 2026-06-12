import { NextRequest, NextResponse } from "next/server";
import { updateInterview, deleteInterview } from "@/lib/db";

export async function PATCH(req: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const body = await req.json();
  const updated = updateInterview(parseInt(id, 10), body);
  if (!updated) return NextResponse.json({ error: "not found" }, { status: 404 });
  return NextResponse.json(updated);
}

export async function DELETE(_req: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  deleteInterview(parseInt(id, 10));
  return new NextResponse(null, { status: 204 });
}
