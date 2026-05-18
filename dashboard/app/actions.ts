"use server";
import { addManualJob, updateJobWorkflowFields } from "@/lib/db";
import { revalidatePath } from "next/cache";

export async function addManualJobAction(formData: FormData) {
  const url = (formData.get("url") as string)?.trim();
  if (!url || !url.startsWith("http")) throw new Error("Invalid URL");
  const result = addManualJob(url);
  revalidatePath("/");
  return result;
}

export async function updateJobAction(
  jobId: number,
  fields: { status?: string; comment?: string; current_interview_status?: string }
) {
  updateJobWorkflowFields(jobId, fields);
  revalidatePath("/");
}
