import { listInterviews } from "@/lib/db";
import { InterviewsClient } from "./InterviewsClient";

export default async function InterviewsPage() {
  const interviews = await listInterviews();
  return (
    <div className="flex flex-col" style={{ height: "calc(100vh - 2.5rem)", background: "var(--bg)", color: "var(--text-1)" }}>
      <InterviewsClient interviews={interviews} />
    </div>
  );
}
