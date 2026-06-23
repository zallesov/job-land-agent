import { InterviewsClient } from "./InterviewsClient";

// Interviews are fetched client-side (via /api/interviews) and kept live via
// PocketBase realtime subscriptions — nothing dynamic is rendered
// server-side, so there's no server/client markup to keep in sync.
export default function InterviewsPage() {
  return (
    <div className="flex flex-col" style={{ height: "calc(100vh - 2.5rem)", background: "var(--bg)", color: "var(--text-1)" }}>
      <InterviewsClient />
    </div>
  );
}
