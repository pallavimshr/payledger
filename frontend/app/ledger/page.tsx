import Link from "next/link";

import { Card, Empty, Mono, PageHeader, TimeAgo } from "@/components/ui";
import { api, money } from "@/lib/api";

export const metadata = { title: "Ledger" };

const GROUPS = [
  { type: "asset", label: "Assets" },
  { type: "liability", label: "Liabilities" },
  { type: "equity", label: "Equity" },
  { type: "revenue", label: "Revenue" },
  { type: "expense", label: "Expenses" },
] as const;

export default async function LedgerPage({ searchParams }: { searchParams: Promise<{ account?: string }> }) {
  const { account } = await searchParams;
  const [accounts, entries] = await Promise.all([api.accounts(), api.entries(account)]);
  const selected = accounts.find((a) => a.code === account);

  return (
    <>
      <PageHeader title="Ledger" subtitle="Double-entry: every entry's debits equal its credits. Click an account to filter." />

      <div className="grid gap-6 lg:grid-cols-5">
        <div className="lg:col-span-2">
          <Card title="Accounts">
            <div className="py-2">
              {GROUPS.map((g) => {
                const list = accounts.filter((a) => a.type === g.type);
                if (list.length === 0) return null;
                return (
                  <div key={g.type} className="py-1">
                    <p className="px-5 pb-1 pt-2 text-xs font-medium uppercase tracking-wide text-zinc-400">{g.label}</p>
                    {list.map((a) => {
                      const active = a.code === account;
                      return (
                        <Link key={a.id} href={active ? "/ledger" : `/ledger?account=${encodeURIComponent(a.code)}`}
                          aria-current={active ? "true" : undefined}
                          className={`mx-2 flex items-center justify-between gap-3 rounded-lg px-3 py-2 text-sm transition-colors ${
                            active ? "bg-zinc-900 text-white" : "hover:bg-zinc-50"}`}>
                          <span className="min-w-0">
                            <span className="block truncate font-medium">{a.name}</span>
                            <span className={`font-mono text-xs ${active ? "text-zinc-400" : "text-zinc-400"}`}>{a.code}</span>
                          </span>
                          <span className={`shrink-0 tabular-nums ${a.balance_paise === 0 && !active ? "text-zinc-300" : ""}`}>
                            {money(a.balance_paise)}
                          </span>
                        </Link>
                      );
                    })}
                  </div>
                );
              })}
            </div>
          </Card>
        </div>

        <div className="lg:col-span-3">
          <Card
            title={selected ? `Entries touching ${selected.name} (${entries.length})` : `Journal entries (${entries.length})`}
            action={selected && <Link href="/ledger" className="text-sm text-zinc-500 hover:text-zinc-900">Show all</Link>}
          >
            {entries.length === 0 ? <Empty>No entries.</Empty> : (
              <ul className="divide-y divide-zinc-100">
                {entries.map((e) => {
                  const lines = [...e.lines].sort((a, b) => (a.direction === b.direction ? 0 : a.direction === "debit" ? -1 : 1));
                  const total = lines.filter((l) => l.direction === "debit").reduce((s, l) => s + l.amount_paise, 0);
                  return (
                    <li key={e.id} className="px-5 py-4">
                      <div className="mb-2 flex items-baseline justify-between gap-4">
                        <p className="text-sm font-medium">{e.description}</p>
                        <p className="shrink-0 text-xs"><TimeAgo iso={e.occurred_at} /></p>
                      </div>
                      <table className="w-full text-xs">
                        <thead><tr className="text-zinc-400"><th className="text-left font-normal">Account</th><th className="w-28 text-right font-normal">Debit</th><th className="w-28 text-right font-normal">Credit</th></tr></thead>
                        <tbody className="font-mono tabular-nums">
                          {lines.map((l, i) => (
                            <tr key={i} className={l.account_code === account ? "bg-amber-50" : ""}>
                              <td className={l.direction === "credit" ? "pl-4 text-zinc-600" : "text-zinc-800"}>{l.account_code}</td>
                              <td className="text-right">{l.direction === "debit" ? money(l.amount_paise) : ""}</td>
                              <td className="text-right">{l.direction === "credit" ? money(l.amount_paise) : ""}</td>
                            </tr>
                          ))}
                          <tr className="border-t border-zinc-100 text-zinc-400">
                            <td className="pt-1">Total</td>
                            <td className="pt-1 text-right">{money(total)}</td>
                            <td className="pt-1 text-right">{money(total)}</td>
                          </tr>
                        </tbody>
                      </table>
                      {e.idempotency_key && <p className="mt-2"><Mono>key: {e.idempotency_key}</Mono></p>}
                    </li>
                  );
                })}
              </ul>
            )}
          </Card>
        </div>
      </div>
    </>
  );
}
