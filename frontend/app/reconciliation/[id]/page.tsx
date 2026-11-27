import Link from "next/link";

import { explainRun, resolveItem } from "@/app/actions";
import { IconSparkle } from "@/components/icons";
import { Card, Mono, PageHeader, ReconBadge, ResolutionBadge, Tabs, Th, TimeAgo, reconStatusLabel } from "@/components/ui";
import { api, money, type ReconItem, type ReconStatus } from "@/lib/api";

export const metadata = { title: "Reconciliation run" };

const ORDER: ReconStatus[] = ["missing_in_ledger", "amount_mismatch", "fee_mismatch", "missing_in_report", "matched"];

const CAUSE_LABEL: Record<string, string> = {
  webhook_missed: "Missed webhook", fee_difference: "Fee difference", amount_error: "Amount error",
  chargeback: "Chargeback", other_adjustment: "Gateway adjustment", pending_settlement: "Pending settlement",
  data_error: "Data error", other: "Other",
};

function Amount({ paise }: { paise: number | null }) {
  return paise === null ? <span className="text-zinc-300">—</span> : <>{money(paise)}</>;
}

function Diff({ a, b }: { a: number | null; b: number | null }) {
  if (a === null || b === null || a === b) return null;
  const d = a - b;  // report minus ledger
  return (
    <span className="ml-2 whitespace-nowrap rounded bg-amber-50 px-1.5 py-0.5 text-xs font-medium text-amber-800"
      title="Razorpay report minus our ledger">
      report {d > 0 ? "+" : "−"}{money(Math.abs(d))}
    </span>
  );
}

function ItemCard({ item }: { item: ReconItem }) {
  const ai = item.ai;
  return (
    <li className="px-5 py-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2">
          <ReconBadge status={item.status} />
          <span className="text-sm font-medium capitalize">{item.entity_type}</span>
          <Mono>{item.entity_id}</Mono>
        </div>
        <ResolutionBadge r={item.resolution} />
      </div>

      <table className="mt-3 w-full max-w-lg text-sm">
        <thead><tr><Th></Th><Th right>Razorpay report</Th><Th right>Our ledger</Th></tr></thead>
        <tbody>
          <tr>
            <td className="py-1 text-zinc-500">Amount</td>
            <td className="py-1 text-right tabular-nums"><Amount paise={item.report_amount_paise} /></td>
            <td className="py-1 text-right tabular-nums"><Amount paise={item.ledger_amount_paise} /><Diff a={item.report_amount_paise} b={item.ledger_amount_paise} /></td>
          </tr>
          {item.entity_type === "payment" && (
            <tr>
              <td className="py-1 text-zinc-500">Fee</td>
              <td className="py-1 text-right tabular-nums"><Amount paise={item.report_fee_paise} /></td>
              <td className="py-1 text-right tabular-nums"><Amount paise={item.ledger_fee_paise} /><Diff a={item.report_fee_paise} b={item.ledger_fee_paise} /></td>
            </tr>
          )}
        </tbody>
      </table>
      {item.report_row?.description && <p className="mt-2 text-xs text-zinc-500">Report note: {item.report_row.description}</p>}

      {ai && (
        <div className="mt-4 rounded-xl border border-violet-200 bg-violet-50/40 p-4">
          <div className="mb-2 flex flex-wrap items-center gap-2 text-xs">
            <span className="inline-flex items-center gap-1 font-medium text-violet-800"><IconSparkle width={14} height={14} /> AI analysis</span>
            {ai.cause && <span className="rounded-full bg-white px-2 py-0.5 text-zinc-700 ring-1 ring-violet-200">{CAUSE_LABEL[ai.cause] ?? ai.cause}</span>}
            {ai.confidence && <span className="text-zinc-500">{ai.confidence} confidence</span>}
          </div>
          {ai.explanation && <p className="text-sm text-zinc-800">{ai.explanation}</p>}
          {ai.error && <p className="mt-2 text-xs text-red-700">{ai.error}</p>}

          {ai.suggestion && (
            <div className="mt-3 rounded-lg bg-white p-3 ring-1 ring-zinc-200">
              <p className="mb-2 text-xs font-medium text-zinc-500">Suggested correction · {ai.suggestion.description}</p>
              <table className="w-full text-xs">
                <tbody className="font-mono tabular-nums">
                  {[...ai.suggestion.lines].sort((a, b) => (a.direction === b.direction ? 0 : a.direction === "debit" ? -1 : 1)).map((l, i) => (
                    <tr key={i}>
                      <td className={l.direction === "credit" ? "pl-4 text-zinc-600" : ""}>{l.account_code}</td>
                      <td className="w-28 text-right">{l.direction === "debit" ? money(l.amount_paise) : ""}</td>
                      <td className="w-28 text-right">{l.direction === "credit" ? money(l.amount_paise) : ""}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <p className="mt-2 text-[11px] text-zinc-400">✓ Checked by PayLedger: balanced, known accounts, within the row amount.</p>
            </div>
          )}
        </div>
      )}

      {item.resolution === "open" && (
        <div className="mt-4 flex gap-2">
          {ai?.suggestion && (
            <form action={resolveItem.bind(null, item.id, "accept")}>
              <button className="rounded-lg bg-zinc-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-zinc-700">Accept &amp; post fix</button>
            </form>
          )}
          <form action={resolveItem.bind(null, item.id, "dismiss")}>
            <button className="rounded-lg bg-white px-3 py-1.5 text-sm ring-1 ring-zinc-300 hover:bg-zinc-50">Dismiss</button>
          </form>
        </div>
      )}
    </li>
  );
}

export default async function RunPage({ params, searchParams }: {
  params: Promise<{ id: string }>; searchParams: Promise<{ show?: string }>;
}) {
  const { id } = await params;
  const { show } = await searchParams;
  const run = await api.recon(id);
  const issues = run.items.filter((i) => i.status !== "matched");
  const needsAi = issues.some((i) => !i.ai || (i.ai.error && !i.ai.explanation));
  const visible = (show === "all" ? run.items : issues)
    .sort((a, b) => ORDER.indexOf(a.status) - ORDER.indexOf(b.status) || a.position - b.position);

  return (
    <>
      <Link href="/reconciliation" className="text-sm text-zinc-500 hover:text-zinc-900">← Reconciliation</Link>
      <div className="mt-2">
        <PageHeader
          title={run.source_filename}
          subtitle={`${run.rows_in_report} report rows · ${run.ai_model ? `explained by ${run.ai_model}` : "no AI analysis yet"}`}
          action={needsAi && (
            <form action={explainRun.bind(null, run.id)}>
              <button className="inline-flex items-center gap-1.5 rounded-lg bg-violet-700 px-3.5 py-2 text-sm font-medium text-white shadow-sm hover:bg-violet-600">
                <IconSparkle width={16} height={16} /> Explain with AI
              </button>
            </form>
          )}
        />
      </div>

      <div className="mb-6 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
        {ORDER.map((s) => (
          <div key={s} className="rounded-xl border border-zinc-200 bg-white px-4 py-3 shadow-sm">
            <p className="text-xs text-zinc-500">{reconStatusLabel(s)}</p>
            <p className="mt-1 text-xl font-semibold tabular-nums">{run.by_status[s] ?? 0}</p>
          </div>
        ))}
      </div>

      <Tabs items={[
        { href: `/reconciliation/${run.id}`, label: "Issues", count: issues.length, active: show !== "all" },
        { href: `/reconciliation/${run.id}?show=all`, label: "All rows", count: run.items.length, active: show === "all" },
      ]} />

      <Card>
        {visible.length === 0 ? (
          <p className="px-5 py-10 text-center text-sm text-good-text">✓ Everything matched. The ledger agrees with Razorpay.</p>
        ) : (
          <ul className="divide-y divide-zinc-100">{visible.map((i) => <ItemCard key={i.id} item={i} />)}</ul>
        )}
      </Card>
      <p className="mt-3 text-xs text-zinc-400">Run <TimeAgo iso={run.created_at} /></p>
    </>
  );
}
