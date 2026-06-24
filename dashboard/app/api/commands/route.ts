import { NextRequest, NextResponse } from "next/server";
import { createResearchCommand, createScreenCommand, getJobDetail, markCommandFailed } from "@/lib/db";
import { unauthorizedResponse } from "@/lib/auth";
import { spawn } from "child_process";
import { openSync } from "fs";
import path from "path";

const ALLOWED_COMMANDS = new Set(["research_job", "screen_job"]);
const HERMES = process.env.HERMES_BIN || "hermes";

const COMMAND_CONFIG: Record<string, {
  skill: string;
  logDir: string;
  promptFn: (jobId: string, commandId: string, dbPath: string) => string;
}> = {
  research_job: {
    skill: "job-research",
    logDir: "research-logs",
    promptFn: (jobId, commandId, dbPath) =>
      `Research job_id=${parseInt(jobId) || jobId} command_id=${commandId} db=${dbPath}`,
  },
  screen_job: {
    skill: "screen-job",
    logDir: "screen-logs",
    promptFn: (jobId, commandId, dbPath) =>
      `Screen job_id=${parseInt(jobId) || jobId} command_id=${commandId} db=${dbPath}`,
  },
};

export async function POST(req: NextRequest) {
  const unauth = unauthorizedResponse();
  if (unauth) return unauth;

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  let body: any;
  try { body = await req.json(); } catch {
    return NextResponse.json({ error: "Invalid JSON" }, { status: 400 });
  }
  const { command_type, job_id } = body;
  if (!ALLOWED_COMMANDS.has(command_type))
    return NextResponse.json({ error: "Command not allowed" }, { status: 400 });
  if (!job_id || typeof job_id !== "string")
    return NextResponse.json({ error: "Invalid job_id" }, { status: 400 });

  const jobData = await getJobDetail(job_id);
  if (!jobData) return NextResponse.json({ error: "Job not found" }, { status: 404 });

  const createCmd = command_type === "screen_job" ? createScreenCommand : createResearchCommand;
  const { commandId, existing } = await createCmd(job_id);

  if (!existing) {
    const cfg = COMMAND_CONFIG[command_type];
    const dbPath = path.resolve(process.cwd(), "../jobs.db");
    const logDir = path.resolve(process.cwd(), `../outputs/${cfg.logDir}`);
    const logFile = path.join(logDir, `job_${job_id}_cmd_${commandId}.log`);
    const prompt = cfg.promptFn(job_id, commandId, dbPath);
    const { mkdirSync } = await import("fs");
    mkdirSync(logDir, { recursive: true });
    const logFd = openSync(logFile, "a");
    const projectRoot = path.resolve(process.cwd(), "..");
    const child = spawn(
      HERMES,
      ["-p", "joblandagent", "--yolo", "--skills", cfg.skill, "-z", prompt],
      { detached: true, stdio: ["ignore", logFd, logFd], cwd: projectRoot }
    );

    child.on("error", async (err) => {
      try {
        await markCommandFailed(commandId, `Failed to start Hermes: ${err.message}. Start the Hermes gateway: hermes -p joblandagent`);
      } catch { /* ignore */ }
    });

    child.on("close", async (code) => {
      if (code !== 0) {
        try {
          await markCommandFailed(commandId,
            `Hermes exited immediately (code ${code ?? "signal"}) — Hermes gateway may not be running. Start it: hermes -p joblandagent`
          );
        } catch { /* ignore */ }
      }
    });

    child.unref();
  }
  return NextResponse.json({ commandId, existing });
}
