"use server";

// Server Actions: functions the browser can trigger (via a <form>) that run on the server.
import { revalidatePath } from "next/cache";

import { post } from "@/lib/api";

export async function retryWebhooks() {
  await post("/webhook-events/retry");
  revalidatePath("/", "layout");
}

export async function cancelOrder(orderId: string) {
  await post(`/orders/${orderId}/cancel`);
  revalidatePath("/", "layout");
}
