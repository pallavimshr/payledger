import { retryWebhooks } from "@/app/actions";
import { Card, Empty, Mono, PageHeader, Tabs, Td, Th, TimeAgo, WebhookBadge } from "@/components/ui";
import { api } from "@/lib/api";

export const metadata = { title: "Webhooks" };

const FILTERS = [
  { status: undefined, label: "All" },
  { status: "failed", label: "Failed" },
  { status: "processed", label: "Processed" },
  { status: "ignored", label: "Ignored" },
] as const;

export default async function WebhooksPage({ searchParams }: { searchParams: Promise<{ status?: string }> }) {
  const { status } = await searchParams;
  const [events, stats] = await Promise.all([api.webhooks(status), api.stats()]);
  const byStatus = stats.webhooks_by_status as Record<string, number | undefined>;
  const total = Object.values(byStatus).reduce<number>((s, n) => s + (n ?? 0), 0);
  const failed = byStatus.failed ?? 0;

  return (
    <>
      <PageHeader
        title="Webhooks"
        subtitle="Every gateway event is stored before processing. Duplicate deliveries are rejected and never appear here."
        action={
          failed > 0 && (
            <form action={retryWebhooks}>
              <button className="rounded-lg bg-zinc-900 px-3.5 py-2 text-sm font-medium text-white shadow-sm transition-colors hover:bg-zinc-700">
                Retry {failed} failed
              </button>
            </form>
          )
        }
      />

      <Tabs items={FILTERS.map((f) => ({
        href: f.status ? `/webhooks?status=${f.status}` : "/webhooks",
        label: f.label,
        count: f.status ? byStatus[f.status] ?? 0 : total,
        active: f.status === status,
      }))} />

      <Card>
        {events.length === 0 ? <Empty>No webhook events here.</Empty> : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="border-b border-zinc-100">
                <tr><Th>Event</Th><Th>Status</Th><Th right>Attempts</Th><Th>Received</Th><Th>Event ID</Th></tr>
              </thead>
              <tbody className="divide-y divide-zinc-100">
                {events.map((e) => (
                  <tr key={`${e.provider}:${e.event_id}`} className={`align-top ${e.status === "failed" ? "bg-red-50/50" : "hover:bg-zinc-50"}`}>
                    <Td>
                      <p className="font-medium">{e.event_type}</p>
                      {e.last_error && <p className="mt-0.5 max-w-md text-xs text-red-700">{e.last_error}</p>}
                      <details className="group mt-1">
                        <summary className="cursor-pointer select-none text-xs text-zinc-400 hover:text-zinc-700">
                          <span className="group-open:hidden">View payload</span>
                          <span className="hidden group-open:inline">Hide payload</span>
                        </summary>
                        <pre className="mt-2 max-h-72 max-w-xl overflow-auto rounded-lg bg-zinc-950 p-3 text-[11px] leading-relaxed text-zinc-100">
                          {JSON.stringify(e.payload, null, 2)}
                        </pre>
                      </details>
                    </Td>
                    <Td><WebhookBadge status={e.status} /></Td>
                    <Td right>{e.attempts}</Td>
                    <Td><TimeAgo iso={e.received_at} /></Td>
                    <Td><Mono>{e.event_id}</Mono></Td>
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
