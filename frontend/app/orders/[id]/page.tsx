import Link from "next/link";

import { cancelOrder } from "@/app/actions";
import { Card, Empty, Mono, OrderBadge, PageHeader, StatusDot, Td, Th, TimeAgo, orderStatusLabel } from "@/components/ui";
import { api, dateTime, money, type OrderStatus } from "@/lib/api";

const label = (s: string) => orderStatusLabel(s as OrderStatus);

export default async function OrderDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const o = await api.order(id);
  const refundedPct = Math.round((o.amount_refunded_paise / o.amount_paise) * 100);
  const canCancel = o.status === "created" || o.status === "failed";

  return (
    <>
      <Link href="/orders" className="text-sm text-zinc-500 hover:text-zinc-900">← Orders</Link>
      <div className="mt-2">
        <PageHeader
          title={o.external_id}
          subtitle={`Created ${dateTime(o.created_at)}`}
          action={
            <div className="flex items-center gap-3">
              <OrderBadge status={o.status} />
              {canCancel && (
                <form action={cancelOrder.bind(null, o.id)}>
                  <button className="rounded-md bg-white px-3 py-1.5 text-sm ring-1 ring-zinc-300 hover:bg-zinc-50">Cancel order</button>
                </form>
              )}
            </div>
          }
        />
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <Card title="Amounts">
          <dl className="space-y-3 px-5 py-4 text-sm">
            <div className="flex justify-between"><dt className="text-zinc-500">Order total</dt><dd className="tabular-nums font-medium">{money(o.amount_paise)}</dd></div>
            <div className="flex justify-between"><dt className="text-zinc-500">Refunded</dt><dd className="tabular-nums">{money(o.amount_refunded_paise)}</dd></div>
            <div className="flex justify-between"><dt className="text-zinc-500">Still refundable</dt><dd className="tabular-nums">{money(o.refundable_paise)}</dd></div>
            <div>
              {/* Meter: share refunded; the track is a lighter step of the same hue */}
              <div className="h-2 overflow-hidden rounded-full bg-blue-100" role="meter" aria-valuenow={refundedPct} aria-valuemin={0} aria-valuemax={100} aria-label="Share refunded">
                <div className="h-full rounded-full bg-blue-500" style={{ width: `${refundedPct}%` }} />
              </div>
              <p className="mt-1 text-xs text-zinc-400">{refundedPct}% refunded</p>
            </div>
          </dl>
          <dl className="space-y-2 border-t border-zinc-100 px-5 py-4 text-sm">
            <div className="flex justify-between gap-2"><dt className="text-zinc-500">Gateway order</dt><dd><Mono>{o.gateway_order_id}</Mono></dd></div>
            <div className="flex justify-between gap-2"><dt className="text-zinc-500">Payment</dt><dd><Mono>{o.gateway_payment_id ?? "—"}</Mono></dd></div>
          </dl>
        </Card>

        <div className="space-y-6 lg:col-span-2">
          <Card title="Timeline">
            <ol className="px-5 py-5">
              {o.history.map((h, i) => (
                <li key={i} className="relative flex gap-4 pb-6 last:pb-0">
                  {i < o.history.length - 1 && <span className="absolute left-[13px] top-8 h-[calc(100%-2rem)] w-px bg-zinc-200" aria-hidden />}
                  <StatusDot status={h.to_status as OrderStatus} note={h.from_status === h.to_status} />
                  <div className="pt-0.5 text-sm">
                    <p className="font-medium">
                      {h.from_status === h.to_status ? "Note" : h.from_status ? `${label(h.from_status)} → ${label(h.to_status)}` : label(h.to_status)}
                    </p>
                    <p className="text-zinc-600">{h.note}</p>
                    <p className="mt-0.5 text-xs"><TimeAgo iso={h.created_at} /></p>
                  </div>
                </li>
              ))}
            </ol>
          </Card>

          <Card title="Refunds">
            {o.refunds.length === 0 ? <Empty>No refunds.</Empty> : (
              <table className="w-full text-sm">
                <thead className="border-b border-zinc-100"><tr><Th>Refund</Th><Th>Date</Th><Th right>Amount</Th></tr></thead>
                <tbody className="divide-y divide-zinc-100">
                  {o.refunds.map((r) => (
                    <tr key={r.gateway_refund_id}>
                      <Td><Mono>{r.gateway_refund_id}</Mono></Td>
                      <Td><span className="text-zinc-500">{dateTime(r.created_at)}</span></Td>
                      <Td right>{money(r.amount_paise)}</Td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </Card>
        </div>
      </div>
    </>
  );
}
