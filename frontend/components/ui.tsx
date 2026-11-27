import Link from "next/link";
import type { ReactNode } from "react";

import { dateTime, timeAgo, type OrderStatus, type WebhookStatus } from "@/lib/api";

export function PageHeader({ title, subtitle, action }: { title: string; subtitle?: string; action?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">{title}</h1>
        {subtitle && <p className="mt-1 text-sm text-zinc-500">{subtitle}</p>}
      </div>
      {action}
    </div>
  );
}

export function Card({ title, children, action }: { title?: string; children: ReactNode; action?: ReactNode }) {
  return (
    <section className="min-w-0 overflow-hidden rounded-xl border border-zinc-200 bg-white shadow-sm">
      {title && (
        <div className="flex items-center justify-between border-b border-zinc-100 px-5 py-3">
          <h2 className="text-sm font-medium text-zinc-700">{title}</h2>
          {action}
        </div>
      )}
      {children}
    </section>
  );
}

/** Stat tile: sentence-case label, semibold value, optional hint. */
export function StatTile({ label, value, hint, icon }: { label: string; value: string; hint?: string; icon?: ReactNode }) {
  return (
    <div className="rounded-xl border border-zinc-200 bg-white p-5 shadow-sm">
      <p className="flex items-center gap-2 text-sm text-zinc-500">{icon}{label}</p>
      <p className="mt-2 text-2xl font-semibold tracking-tight tabular-nums">{value}</p>
      {hint && <p className="mt-1 text-xs text-zinc-400">{hint}</p>}
    </div>
  );
}

type Tone = "good" | "warning" | "critical" | "neutral" | "info";

const TONES: Record<Tone, string> = {
  good: "bg-green-50 text-good-text ring-good/30",
  warning: "bg-amber-50 text-amber-800 ring-warning/50",
  critical: "bg-red-50 text-red-700 ring-critical/30",
  info: "bg-blue-50 text-blue-700 ring-blue-300/50",
  neutral: "bg-zinc-100 text-zinc-600 ring-zinc-300/60",
};

// Every status = icon + label + color, so meaning never depends on color alone.
const ORDER_STATUS: Record<OrderStatus, { label: string; icon: string; tone: Tone }> = {
  created: { label: "Awaiting payment", icon: "○", tone: "neutral" },
  paid: { label: "Paid", icon: "✓", tone: "good" },
  partially_refunded: { label: "Partially refunded", icon: "½", tone: "warning" },
  refunded: { label: "Refunded", icon: "↺", tone: "info" },
  failed: { label: "Payment failed", icon: "✕", tone: "critical" },
  cancelled: { label: "Cancelled", icon: "⊘", tone: "neutral" },
};

const WEBHOOK_STATUS: Record<WebhookStatus, { label: string; icon: string; tone: Tone }> = {
  received: { label: "Pending", icon: "…", tone: "info" },
  processed: { label: "Processed", icon: "✓", tone: "good" },
  ignored: { label: "Ignored", icon: "–", tone: "neutral" },
  failed: { label: "Failed", icon: "!", tone: "critical" },
};

function Badge({ label, icon, tone }: { label: string; icon: string; tone: Tone }) {
  return (
    <span className={`inline-flex items-center gap-1.5 whitespace-nowrap rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset ${TONES[tone]}`}>
      <span aria-hidden>{icon}</span>
      {label}
    </span>
  );
}

export const OrderBadge = ({ status }: { status: OrderStatus }) => <Badge {...ORDER_STATUS[status]} />;

const DOT: Record<Tone, string> = {
  good: "bg-green-50 text-good-text ring-good/40",
  warning: "bg-amber-50 text-amber-800 ring-warning/60",
  critical: "bg-red-50 text-red-700 ring-critical/40",
  info: "bg-blue-50 text-blue-700 ring-blue-300",
  neutral: "bg-zinc-50 text-zinc-500 ring-zinc-300",
};

/** Round status icon used on the order timeline; `note` = incident without a status change. */
export function StatusDot({ status, note }: { status: OrderStatus; note?: boolean }) {
  const meta = note ? { icon: "i", tone: "warning" as Tone } : ORDER_STATUS[status];
  return (
    <span className={`grid h-7 w-7 shrink-0 place-items-center rounded-full text-xs font-semibold ring-1 ring-inset ${DOT[meta.tone]}`} aria-hidden>
      {meta.icon}
    </span>
  );
}
export const WebhookBadge = ({ status }: { status: WebhookStatus }) => <Badge {...WEBHOOK_STATUS[status]} />;
export const orderStatusLabel = (s: OrderStatus) => ORDER_STATUS[s].label;

/** Relative time ("5 min ago") with the exact date on hover. */
export function TimeAgo({ iso }: { iso: string }) {
  return (
    <time dateTime={iso} title={dateTime(iso)} className="whitespace-nowrap text-zinc-500">
      {timeAgo(iso)}
    </time>
  );
}

/** Pill-style tabs driven by the URL, so filters are linkable and survive refresh. */
export function Tabs({ items }: { items: { href: string; label: string; count?: number; active: boolean }[] }) {
  return (
    <div className="mb-4 flex flex-wrap gap-2" role="tablist">
      {items.map((t) => (
        <Link key={t.href} href={t.href} role="tab" aria-selected={t.active}
          className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-sm ring-1 ring-inset transition-colors ${
            t.active ? "bg-zinc-900 text-white ring-zinc-900" : "bg-white text-zinc-600 ring-zinc-200 hover:bg-zinc-50"}`}>
          {t.label}
          {t.count !== undefined && (
            <span className={`tabular-nums text-xs ${t.active ? "text-zinc-300" : "text-zinc-400"}`}>{t.count}</span>
          )}
        </Link>
      ))}
    </div>
  );
}

export function Mono({ children }: { children: ReactNode }) {
  return <span className="font-mono text-xs text-zinc-500">{children}</span>;
}

export function Empty({ children }: { children: ReactNode }) {
  return <p className="px-5 py-10 text-center text-sm text-zinc-400">{children}</p>;
}

export function Th({ children, right }: { children?: ReactNode; right?: boolean }) {
  return (
    <th className={`px-5 py-2.5 text-xs font-medium uppercase tracking-wide text-zinc-400 ${right ? "text-right" : "text-left"}`}>
      {children}
    </th>
  );
}

export function Td({ children, right }: { children?: ReactNode; right?: boolean }) {
  return <td className={`px-5 py-3 ${right ? "whitespace-nowrap text-right tabular-nums" : ""}`}>{children}</td>;
}

export function TextLink({ href, children }: { href: string; children: ReactNode }) {
  return <Link href={href} className="whitespace-nowrap text-sm font-medium text-zinc-900 underline-offset-4 hover:underline">{children}</Link>;
}
