import type { Metadata } from "next";
import type { ReactNode } from "react";

import { ApiStatus } from "@/components/api-status";
import { Logo } from "@/components/icons";
import { Nav } from "@/components/nav";
import "./globals.css";

// Live financial data: always render on request, never pre-render at build time.
export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: { default: "PayLedger", template: "%s · PayLedger" },
  description: "Double-entry payments ledger dashboard",
};

function Brand() {
  return (
    <div className="flex items-center gap-2.5">
      <Logo />
      <div className="leading-tight">
        <p className="text-sm font-semibold tracking-tight">PayLedger</p>
        <p className="text-xs text-zinc-400">Payments ledger</p>
      </div>
    </div>
  );
}

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>
        <div className="flex min-h-screen">
          <aside className="sticky top-0 hidden h-screen w-60 shrink-0 flex-col border-r border-zinc-200 bg-white px-3 py-5 md:flex">
            <div className="mb-7 px-2"><Brand /></div>
            <Nav />
            <div className="mt-auto"><ApiStatus /></div>
          </aside>
          <div className="min-w-0 flex-1">
            <header className="flex flex-col gap-3 border-b border-zinc-200 bg-white px-4 py-3 md:hidden">
              <Brand />
              <Nav horizontal />
            </header>
            <main className="px-4 py-6 md:px-10 md:py-9">
              <div className="mx-auto max-w-6xl">{children}</div>
            </main>
          </div>
        </div>
      </body>
    </html>
  );
}
