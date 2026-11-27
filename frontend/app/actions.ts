"use server";

// Server Actions: functions the browser can trigger (via a <form>) that run on the server.
import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";

import { ApiError, post } from "@/lib/api";

export async function retryWebhooks() {
  await post("/webhook-events/retry");
  revalidatePath("/", "layout");
}

export async function cancelOrder(orderId: string) {
  await post(`/orders/${orderId}/cancel`);
  revalidatePath("/", "layout");
}

export type UploadState = { error?: string };

export async function uploadReport(_prev: UploadState, formData: FormData): Promise<UploadState> {
  const file = formData.get("file");
  if (!(file instanceof File) || file.size === 0) return { error: "Choose a CSV file first." };
  const body = new FormData();
  body.append("file", file, file.name);
  let runId: string;
  try {
    runId = (await post<{ id: string }>("/reconciliations", body)).id;
  } catch (e) {
    return { error: e instanceof ApiError ? e.message : "Upload failed. Is the API running?" };
  }
  revalidatePath("/reconciliation");
  redirect(`/reconciliation/${runId}`);  // outside try: redirect works by throwing
}

export async function resolveItem(itemId: string, action: "accept" | "dismiss") {
  await post(`/reconciliation-items/${itemId}/${action}`);
  revalidatePath("/", "layout");
}

export async function explainRun(runId: string) {
  await post(`/reconciliations/${runId}/explain`);
  revalidatePath(`/reconciliation/${runId}`);
}
