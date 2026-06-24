import { NextRequest, NextResponse } from "next/server";
import { getCommand } from "@/lib/db";
import { unauthorizedResponse } from "@/lib/auth";
import { readdirSync, readFileSync } from "fs";
import path from "path";
import os from "os";

const SESSIONS_DIR = path.join(os.homedir(), ".hermes", "sessions");

export async function GET(
  _req: NextRequest,
  { params }: { params: { id: string } }
) {
  const unauth = unauthorizedResponse();
  if (unauth) return unauth;

  const { id } = params;
  const cmd = await getCommand(id);
  if (!cmd) return NextResponse.json({ error: "Command not found" }, { status: 404 });

  const cmdTs = new Date(cmd.created_at.replace(" ", "T") + "Z").getTime();
  let sessionMessages: unknown[] = [];
  let sessionFile: string | null = null;

  try {
    const files = readdirSync(SESSIONS_DIR).filter(f => f.startsWith("session_") && f.endsWith(".json"));
    const match = files.find(f => {
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

  return NextResponse.json({ command: cmd, session_file: sessionFile, messages: sessionMessages });
}
