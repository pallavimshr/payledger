// Typed access to the PayLedger API. Runs on the server (React Server Components),
// so the browser never talks to the backend directly.
export const API_URL = process.env.API_URL ?? "http://localhost:8000";

export type OrderStatus =
  | "created" | "paid" | "partially_refunded" | "refunded" | "failed" | "cancelled";
export type WebhookStatus = "received" | "processed" | "ignored" | "failed";

export interface Stats {
  revenue_paise: number;
  fees_paise: number;
  gateway_held_paise: number;
  bank_paise: number;
  refunded_paise: number;
  journal_entries: number;
  orders_total: number;
  orders_by_status: Partial<Record<OrderStatus, number>>;
  webhooks_by_status: Partial<Record<WebhookStatus, number>>;
}

export interface Account {
  id: string;
  code: string;
  name: string;
  type: "asset" | "liability" | "equity" | "revenue" | "expense";
  balance_paise: number;
}

export interface Order {
  id: string;
  external_id: string;
  amount_paise: number;
  amount_refunded_paise: number;
  refundable_paise: number;
  status: OrderStatus;
  gateway_order_id: string;
  gateway_payment_id: string | null;
  created_at: string;
}

export interface OrderDetail extends Order {
  history: { from_status: string | null; to_status: string; note: string; created_at: string }[];
  refunds: { gateway_refund_id: string; amount_paise: number; created_at: string }[];
}

export interface WebhookEvent {
  payload: unknown;
  event_id: string;
  provider: string;
  event_type: string;
  status: WebhookStatus;
  attempts: number;
  last_error: string | null;
  received_at: string;
  processed_at: string | null;
}

export interface JournalEntry {
  id: string;
  description: string;
  idempotency_key: string | null;
  occurred_at: string;
  lines: { account_code: string; direction: "debit" | "credit"; amount_paise: number }[];
}

export type ReconStatus = "matched" | "amount_mismatch" | "fee_mismatch" | "missing_in_ledger" | "missing_in_report";
export type Resolution = "open" | "accepted" | "dismissed" | "none";

export interface SuggestedEntry {
  description: string;
  lines: { account_code: string; direction: "debit" | "credit"; amount_paise: number }[];
}

export interface ReconItem {
  id: string;
  position: number;
  entity_type: "payment" | "refund" | "adjustment";
  entity_id: string;
  status: ReconStatus;
  resolution: Resolution;
  report_amount_paise: number | null;
  ledger_amount_paise: number | null;
  report_fee_paise: number | null;
  ledger_fee_paise: number | null;
  report_row: Record<string, string> | null;
  ai: null | {
    explanation: string | null;
    cause: string | null;
    confidence: "low" | "medium" | "high" | null;
    suggestion: SuggestedEntry | null;
    error: string | null;
  };
}

export interface ReconRun {
  id: string;
  source_filename: string;
  rows_in_report: number;
  ai_model: string | null;
  created_at: string;
  by_status: Partial<Record<ReconStatus, number>>;
  open_items: number;
}

export interface ReconRunDetail extends ReconRun {
  items: ReconItem[];
}

export class ApiError extends Error {}

async function get<T>(path: string): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, { cache: "no-store" });
  } catch {
    throw new ApiError(`Can't reach the API at ${API_URL}. Is it running? (make dev)`);
  }
  if (!res.ok) throw new ApiError(`${path} returned ${res.status}`);
  return res.json() as Promise<T>;
}

export async function post<T>(path: string, body?: FormData): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, { method: "POST", cache: "no-store", body });
  if (!res.ok) throw new ApiError((await res.json().catch(() => ({})))?.detail ?? `${path} failed`);
  return res.json() as Promise<T>;
}

const qs = (params: Record<string, string | undefined>) => {
  const p = new URLSearchParams({ limit: "200" });
  for (const [k, v] of Object.entries(params)) if (v) p.set(k, v);
  return p.toString();
};

export const api = {
  health: async () => {
    try {
      const res = await fetch(`${API_URL}/health`, { cache: "no-store", signal: AbortSignal.timeout(1500) });
      return res.ok;
    } catch {
      return false;
    }
  },
  stats: () => get<Stats>("/stats"),
  accounts: () => get<Account[]>("/accounts"),
  orders: (status?: string, q?: string) => get<Order[]>(`/orders?${qs({ status, q })}`),
  order: (id: string) => get<OrderDetail>(`/orders/${id}`),
  webhooks: (status?: string) => get<WebhookEvent[]>(`/webhook-events?${qs({ status })}`),
  entries: (account?: string) => get<JournalEntry[]>(`/journal-entries?${qs({ account })}`),
  recons: () => get<ReconRun[]>("/reconciliations"),
  recon: (id: string) => get<ReconRunDetail>(`/reconciliations/${id}`),
};

// ---- formatting ----
const inr = new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR" });
const inrCompact = new Intl.NumberFormat("en-IN", {
  style: "currency", currency: "INR", notation: "compact", maximumFractionDigits: 1,
});

/** 123456 paise -> "₹1,234.56" */
export const money = (paise: number) => inr.format(paise / 100);
/** 12345600 paise -> "₹1.2L" style compact figure for stat tiles */
export const moneyCompact = (paise: number) =>
  Math.abs(paise) < 1_00_000_00 ? inr.format(paise / 100) : inrCompact.format(paise / 100); // compact from ₹1 lakh

/** Parse an API timestamp; one without a timezone is UTC (SQLite drops the offset). */
const parseIso = (iso: string) => new Date(/([zZ]|[+-]\d\d:?\d\d)$/.test(iso) ? iso : `${iso}Z`);

export const dateTime = (iso: string) =>
  parseIso(iso).toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short", timeZone: "Asia/Kolkata" });

const rtf = new Intl.RelativeTimeFormat("en", { numeric: "auto" });
/** "just now", "5 min ago", "yesterday", ... */
export function timeAgo(iso: string, now = Date.now()): string {
  const sec = Math.round((parseIso(iso).getTime() - now) / 1000);
  const abs = Math.abs(sec);
  if (abs < 45) return "just now";
  if (abs < 3600) return rtf.format(Math.round(sec / 60), "minute");
  if (abs < 86400) return rtf.format(Math.round(sec / 3600), "hour");
  if (abs < 86400 * 7) return rtf.format(Math.round(sec / 86400), "day");
  return dateTime(iso);
}
