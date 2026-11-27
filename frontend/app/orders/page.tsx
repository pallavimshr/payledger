import Link from "next/link";

import { IconSearch } from "@/components/icons";
import { Card, Empty, Mono, OrderBadge, PageHeader, Tabs, Td, TextLink, Th, TimeAgo, orderStatusLabel } from "@/components/ui";
import { api, money, type OrderStatus } from "@/lib/api";

export const metadata = { title: "Orders" };

const FILTERS: (OrderStatus | undefined)[] = [undefined, "paid", "partially_refunded", "refunded", "created", "failed", "cancelled"];

export default async function OrdersPage({ searchParams }: { searchParams: Promise<{ status?: string; q?: string }> }) {
  const { status, q } = await searchParams;
  const [orders, stats] = await Promise.all([api.orders(status, q), api.stats()]);
  const href = (s?: string) => {
    const p = new URLSearchParams();
    if (s) p.set("status", s);
    if (q) p.set("q", q);
    const str = p.toString();
    return str ? `/orders?${str}` : "/orders";
  };

  return (
    <>
      <PageHeader title="Orders" subtitle={`${orders.length} order${orders.length === 1 ? "" : "s"}${q ? ` matching “${q}”` : ""}`} />

      <form action="/orders" className="mb-4 flex max-w-md items-center gap-2 rounded-lg border border-zinc-200 bg-white px-3 shadow-sm focus-within:ring-2 focus-within:ring-zinc-900/10">
        <IconSearch className="text-zinc-400" />
        {status && <input type="hidden" name="status" value={status} />}
        <input name="q" defaultValue={q} placeholder="Search order no., order ID or payment ID"
          aria-label="Search orders" className="h-10 flex-1 bg-transparent text-sm outline-none placeholder:text-zinc-400" />
        {q && <Link href={status ? `/orders?status=${status}` : "/orders"} className="text-xs text-zinc-400 hover:text-zinc-900">Clear</Link>}
      </form>

      <Tabs items={FILTERS.map((f) => ({
        href: href(f),
        label: f ? orderStatusLabel(f) : "All",
        count: f ? stats.orders_by_status[f] ?? 0 : stats.orders_total,
        active: f === status,
      }))} />

      <Card>
        {orders.length === 0 ? <Empty>No orders match.</Empty> : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="border-b border-zinc-100">
                <tr><Th>Order</Th><Th>Status</Th><Th>Payment</Th><Th right>Amount</Th><Th right>Refunded</Th><Th>Created</Th></tr>
              </thead>
              <tbody className="divide-y divide-zinc-100">
                {orders.map((o) => (
                  <tr key={o.id} className="hover:bg-zinc-50">
                    <Td><TextLink href={`/orders/${o.id}`}>{o.external_id}</TextLink></Td>
                    <Td><OrderBadge status={o.status} /></Td>
                    <Td><Mono>{o.gateway_payment_id ?? "—"}</Mono></Td>
                    <Td right>{money(o.amount_paise)}</Td>
                    <Td right>{o.amount_refunded_paise ? money(o.amount_refunded_paise) : <span className="text-zinc-300">—</span>}</Td>
                    <Td><TimeAgo iso={o.created_at} /></Td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </>
  );
}
