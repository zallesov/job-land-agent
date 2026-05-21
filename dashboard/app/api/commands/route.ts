import { NextRequest, NextResponse } from "next/server";
import { createResearchCommand, createApplyCommand, getDb } from "@/lib/db";
import { spawn } from "child_process";
import { openSync } from "fs";
import path from "path";

const ALLOWED_COMMANDS = new Set(["research_job", "apply_job"]);
const HERMES = "/Users/zall/.local/bin/interviewprep";

const COMMAND_CONFIG: Record<string, { skill: string; logDir: string; promptFn: (jobId: number, commandId: number, dbPath: string) => string }> = {
  research_job: {
    skill: "job-research",
    logDir: "research-logs",
    promptFn: (jobId, commandId, dbPath) => `Research job_id=${jobId} command_id=${commandId} db=${dbPath}`,
  },
  apply_job: {
    skill: "apply-job",
    logDir: "apply-logs",
    promptFn: (jobId, commandId, dbPath) => `Apply job_id=${jobId} command_id=${commandId} db=${dbPath}`,
  },
};

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

  const createCmd = command_type === "apply_job" ? createApplyCommand : createResearchCommand;
  const { commandId, existing } = createCmd(job_id);
  if (!existing) {
    const cfg = COMMAND_CONFIG[command_type];
    const dbPath = path.resolve(process.cwd(), "../jobs.db");
    const logDir = path.resolve(process.cwd(), `../outputs/${cfg.logDir}`);
    const logFile = path.join(logDir, `job_${job_id}_cmd_${commandId}.log`);
    const prompt = cfg.promptFn(job_id, commandId, dbPath);
    const { mkdirSync } = await import("fs");
    mkdirSync(logDir, { recursive: true });
    const logFd = openSync(logFile, "a");
    const child = spawn(
      HERMES,
      ["--yolo", "--skills", cfg.skill, "-z", prompt],
      { detached: true, stdio: ["ignore", logFd, logFd] }
    );
    child.unref();
  }
  return NextResponse.json({ commandId, existing });
}
