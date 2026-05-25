"use server";
import { addManualJob, updateJobWorkflowFields, createScrapeCommand } from "@/lib/db";
import { revalidatePath } from "next/cache";
import { spawn } from "child_process";
import { openSync, mkdirSync } from "fs";
import path from "path";

const HERMES = "/Users/zall/.local/bin/interviewprep";

export async function addManualJobAction(formData: FormData) {
  const url = (formData.get("url") as string)?.trim();
  if (!url || !url.startsWith("http")) throw new Error("Invalid URL");
  const { id: jobId } = addManualJob(url);
  const { commandId } = createScrapeCommand(jobId, url);

  const dbPath = path.resolve(process.cwd(), "../jobs.db");
  const logDir = path.resolve(process.cwd(), "../outputs/research-logs");
  const logFile = path.join(logDir, `job_${jobId}_scrape_${commandId}.log`);
  mkdirSync(logDir, { recursive: true });
  const logFd = openSync(logFile, "a");
  const prompt = `job_id=${jobId} command_id=${commandId} url=${url} db=${dbPath}`;
  const child = spawn(
    HERMES,
    ["--yolo", "--skills", "scrape-and-research-job", "-z", prompt],
    { detached: true, stdio: ["ignore", logFd, logFd] }
  );
  child.unref();

  revalidatePath("/");
  return { id: jobId };
}

export async function updateJobAction(
  jobId: number,
  fields: { user_status?: string; comment?: string }
) {
  updateJobWorkflowFields(jobId, fields);
  revalidatePath("/");
}
