import { NextRequest, NextResponse } from "next/server";
import { getDb } from "@/lib/db";
import { readdirSync, readFileSync } from "fs";
import path from "path";
import os from "os";

const SESSIONS_DIR = path.join(os.homedir(), ".hermes", "sessions");

export async function GET(
  _req: NextRequest,
  { params }: { params: { id: string } }
) {
  const commandId = parseInt(params.id, 10);
  if (!Number.isInteger(commandId)) return NextResponse.json({ error: "Invalid id" }, { status: 400 });

  const db = getDb();
  const cmd = db.prepare("SELECT * FROM agent_commands WHERE id = ?").get(commandId) as {
    id: number; command_type: string; status: string; created_at: string;
    started_at: string | null; finished_at: string | null; error: string | null;
    result_json: string | null; payload_json: string | null;
  } | undefined;
  if (!cmd) return NextResponse.json({ error: "Command not found" }, { status: 404 });

  // Find session file: created within 60s after the command's created_at
  // Session filename: session_YYYYMMDD_HHMMSS_<random>.json
  const cmdTs = new Date(cmd.created_at.replace(" ", "T") + "Z").getTime();
  let sessionMessages: unknown[] = [];
  let sessionFile: string | null = null;

  try {
    const files = readdirSync(SESSIONS_DIR).filter(f => f.startsWith("session_") && f.endsWith(".json"));
    const match = files.find(f => {
      // session_20260525_172233_abc123.json
      const m = f.match(/^session_(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})_/);
      if (!m) return false;
      const fileTs = Date.UTC(+m[1], +m[2] - 1, +m[3], +m[4], +m[5], +m[6]);
      return fileTs >= cmdTs - 5000 && fileTs <= cmdTs + 120000;
    });
    if (match) {
      sessionFile = match;
      const raw = JSON.parse(readFileSync(path.join(SESSIONS_DIR, match), "utf8"));
      sessionMessages = raw.messages ?? [];
    }
  } catch {
    // sessions dir unreadable — return command info only
  }

  return NextResponse.json({
    command: cmd,
    session_file: sessionFile,
    messages: sessionMessages,
  });
}
