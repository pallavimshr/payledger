import Link from "next/link";

import { Card, Empty, PageHeader, ReconBadge, Td, TextLink, Th, TimeAgo } from "@/components/ui";
import { UploadForm } from "@/components/upload-form";
import { api, type ReconStatus } from "@/lib/api";

export const metadata = { title: "Reconciliation" };

const ISSUES: ReconStatus[] = ["amount_mismatch", "fee_mismatch", "missing_in_ledger", "missing_in_report"];

export default async function ReconciliationPage() {
  const runs = await api.recons();

  return (
    <>
      <PageHeader
        title="Reconciliation"
        subtitle="Compare Razorpay's settlement report with your ledger. Code finds the mismatches; AI explains them; you approve every fix."
      />

      <div className="grid gap-6 lg:grid-cols-3">
        <Card title="New reconciliation">
          <div className="space-y-4 px-5 py-5">
            <UploadForm />
            <p className="text-xs text-zinc-500">
              No report yet?{" "}
              <a href="/reconciliation/sample" className="font-medium text-zinc-900 underline underline-offset-4">
                Download a sample
              </a>{" "}
              built from your ledger, with a few planted problems for the AI to find.
            </p>
          </div>
        </Card>

        <div className="min-w-0 lg:col-span-2">
          <Card title="Past runs">
            {runs.length === 0 ? <Empty>No reconciliations yet.</Empty> : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="border-b border-zinc-100">
                    <tr><Th>Report</Th><Th>Issues</Th><Th right>Open</Th><Th>Run</Th></tr>
                  </thead>
                  <tbody className="divide-y divide-zinc-100">
                    {runs.map((r) => {
                      const issues = ISSUES.filter((s) => (r.by_status[s] ?? 0) > 0);
                      return (
                        <tr key={r.id} className="align-top hover:bg-zinc-50">
                          <Td>
                            <TextLink href={`/reconciliation/${r.id}`}>{r.source_filename}</TextLink>
                            <p className="text-xs text-zinc-400">{r.rows_in_report} rows · {r.by_status.matched ?? 0} matched</p>
                          </Td>
                          <Td>
                            <div className="flex flex-wrap gap-1.5">
                              {issues.length === 0 ? <ReconBadge status="matched" /> :
                                issues.map((s) => (
                                  <Link key={s} href={`/reconciliation/${r.id}`} className="inline-flex items-center gap-1">
                                    <ReconBadge status={s} /><span className="text-xs tabular-nums text-zinc-500">×{r.by_status[s]}</span>
                                  </Link>
                                ))}
                            </div>
                          </Td>
                          <Td right>{r.open_items}</Td>
                          <Td><TimeAgo iso={r.created_at} /></Td>
                        </tr>
                      );
                    })}
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
