import { NextRequest, NextResponse } from "next/server";
import { updateInterview, deleteInterview } from "@/lib/db";
import { unauthorizedResponse } from "@/lib/auth";

export async function PATCH(req: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const unauth = unauthorizedResponse();
  if (unauth) return unauth;

  const { id } = await params;
  const body = await req.json();
  const updated = await updateInterview(id, body);
  if (!updated) return NextResponse.json({ error: "not found" }, { status: 404 });
  return NextResponse.json(updated);
}

export async function DELETE(_req: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const unauth = unauthorizedResponse();
  if (unauth) return unauth;

  const { id } = await params;
  await deleteInterview(id);
  return new NextResponse(null, { status: 204 });
}
