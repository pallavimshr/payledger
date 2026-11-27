import Link from "next/link";

import { IconChevron } from "@/components/icons";
import { MoneyFlow } from "@/components/money-flow";
import { Card, Empty, Mono, OrderBadge, PageHeader, StatTile, Td, TextLink, Th, TimeAgo, orderStatusLabel } from "@/components/ui";
import { api, money, moneyCompact, type OrderStatus } from "@/lib/api";

const STATUS_ORDER: OrderStatus[] = ["paid", "partially_refunded", "refunded", "created", "failed", "cancelled"];

export default async function Overview() {
  const [stats, accounts, orders] = await Promise.all([api.stats(), api.accounts(), api.orders()]);

  // The double-entry check: debit-normal balances must equal credit-normal balances.
  const debitSide = accounts.filter((a) => a.type === "asset" || a.type === "expense")
    .reduce((s, a) => s + a.balance_paise, 0);
  const creditSide = accounts.filter((a) => a.type !== "asset" && a.type !== "expense")
    .reduce((s, a) => s + a.balance_paise, 0);
  const balanced = debitSide === creditSide;
  const failedWebhooks = stats.webhooks_by_status.failed ?? 0;
  const paidOrders = (stats.orders_by_status.paid ?? 0) + (stats.orders_by_status.partially_refunded ?? 0)
    + (stats.orders_by_status.refunded ?? 0);
  const maxCount = Math.max(1, ...STATUS_ORDER.map((s) => stats.orders_by_status[s] ?? 0));

  return (
    <>
      <PageHeader
        title="Overview"
        subtitle="Where every rupee is, right now."
        action={
          <div className={`flex items-center gap-2 whitespace-nowrap rounded-full px-3 py-1.5 text-sm ring-1 ring-inset ${
            balanced ? "bg-green-50 text-good-text ring-good/30" : "bg-red-50 text-red-700 ring-critical/30"}`}
            title={`Debits ${money(debitSide)} · Credits ${money(creditSide)}`}>
            <span aria-hidden>{balanced ? "✓" : "!"}</span>
            <span className="font-medium">{balanced ? "Books balanced" : "Books NOT balanced"}</span>
          </div>
        }
      />

      {failedWebhooks > 0 && (
        <Link href="/webhooks?status=failed" className="mb-6 flex items-center gap-3 rounded-xl border border-red-200 bg-red-50/60 px-5 py-3 text-sm transition-colors hover:bg-red-50">
          <span aria-hidden className="grid h-6 w-6 place-items-center rounded-full bg-critical text-xs font-bold text-white">!</span>
          <span className="flex-1">
            <span className="font-medium">{failedWebhooks} failed webhook event{failedWebhooks > 1 ? "s" : ""}</span>{" "}
            {failedWebhooks > 1 ? "need" : "needs"} attention
          </span>
          <IconChevron className="text-zinc-400" />
        </Link>
      )}

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatTile label="Net revenue" value={moneyCompact(stats.revenue_paise)} hint="Sales minus refunds" />
        <StatTile label="Held by gateway" value={moneyCompact(stats.gateway_held_paise)} hint="Captured, not yet settled" />
        <StatTile label="Settled to bank" value={moneyCompact(stats.bank_paise)} hint="Paid out by the gateway" />
        <StatTile label="Paid orders" value={paidOrders.toLocaleString("en-IN")} hint={`of ${stats.orders_total} total`} />
      </div>

      <div className="mt-6">
        <Card title="Where the money went">
          <MoneyFlow values={{
            bank: stats.bank_paise,
            held: stats.gateway_held_paise,
            refunded: stats.refunded_paise,
            fees: stats.fees_paise,
          }} />
        </Card>
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-3">
        <Card title="Orders by status">
          <ul className="space-y-3 px-5 py-4 text-sm">
            {STATUS_ORDER.map((s) => {
              const n = stats.orders_by_status[s] ?? 0;
              return (
                <li key={s}>
                  <Link href={`/orders?status=${s}`} className="group block">
                    <div className="flex justify-between">
                      <span className="text-zinc-600 group-hover:text-zinc-900">{orderStatusLabel(s)}</span>
                      <span className="tabular-nums font-medium">{n}</span>
                    </div>
                    {/* thin meter: same blue hue, lighter track */}
                    <div className="mt-1.5 h-1.5 rounded-full bg-blue-50">
                      <div className="h-full rounded-full bg-[#257de0]" style={{ width: `${(n / maxCount) * 100}%` }} />
                    </div>
                  </Link>
                </li>
              );
            })}
          </ul>
        </Card>

        <div className="min-w-0 lg:col-span-2">
          <Card title="Recent orders" action={<TextLink href="/orders">View all</TextLink>}>
            {orders.length === 0 ? (
              <Empty>No orders yet. Run <Mono>make demo</Mono> to add sample data.</Empty>
            ) : (
              <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="border-b border-zinc-100"><tr><Th>Order</Th><Th>Status</Th><Th>Created</Th><Th right>Amount</Th></tr></thead>
                <tbody className="divide-y divide-zinc-100">
                  {orders.slice(0, 7).map((o) => (
                    <tr key={o.id} className="hover:bg-zinc-50">
                      <Td><TextLink href={`/orders/${o.id}`}>{o.external_id}</TextLink></Td>
                      <Td><OrderBadge status={o.status} /></Td>
                      <Td><TimeAgo iso={o.created_at} /></Td>
                      <Td right>{money(o.amount_paise)}</Td>
                    </tr>
                  ))}
                </tbody>
              </table>
              </div>
            )}
          </Card>
        </div>
      </div>
    </>
  );
}
