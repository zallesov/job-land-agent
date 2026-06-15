import { unstable_noStore as noStore } from "next/cache";
import { listInterviews } from "@/lib/db";
import { InterviewsClient } from "./InterviewsClient";

export const dynamic = "force-dynamic";
export const revalidate = 0;

export default async function InterviewsPage() {
  noStore();
  const interviews = await listInterviews();
  return (
    <div className="flex flex-col" style={{ height: "calc(100vh - 2.5rem)", background: "var(--bg)", color: "var(--text-1)" }}>
      <InterviewsClient interviews={interviews} />
    </div>
  );
}
