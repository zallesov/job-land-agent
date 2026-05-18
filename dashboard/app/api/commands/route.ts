import { NextRequest, NextResponse } from "next/server";
import { createResearchCommand, getDb } from "@/lib/db";
import { spawn } from "child_process";
import path from "path";

const ALLOWED_COMMANDS = new Set(["research_job"]);

export async function POST(req: NextRequest) {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  let body: any;
  try { body = await req.json(); } catch {
    return NextResponse.json({ error: "Invalid JSON" }, { status: 400 });
  }
  const { command_type, job_id } = body;
  if (!ALLOWED_COMMANDS.has(command_type))
    return NextResponse.json({ error: "Command not allowed" }, { status: 400 });
  if (!Number.isInteger(job_id))
    return NextResponse.json({ error: "Invalid job_id" }, { status: 400 });

  const db = getDb();
  const job = db.prepare("SELECT id FROM jobs WHERE id = ?").get(job_id);
  if (!job) return NextResponse.json({ error: "Job not found" }, { status: 404 });

  const { commandId, existing } = createResearchCommand(job_id);
  if (!existing) {
    const scriptPath = path.resolve(process.cwd(), "../scripts/research_job.py");
    const dbPath = path.resolve(process.cwd(), "../jobs.db");
    const child = spawn("python3", [scriptPath, "--db", dbPath, "--job-id", String(job_id), "--command-id", String(commandId)],
      { detached: true, stdio: "ignore" });
    child.unref();
  }
  return NextResponse.json({ commandId, existing });
}
