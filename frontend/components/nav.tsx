"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { IconLedger, IconOrders, IconOverview, IconReconcile, IconWebhook } from "@/components/icons";

const LINKS = [
  { href: "/", label: "Overview", Icon: IconOverview },
  { href: "/orders", label: "Orders", Icon: IconOrders },
  { href: "/ledger", label: "Ledger", Icon: IconLedger },
  { href: "/webhooks", label: "Webhooks", Icon: IconWebhook },
  { href: "/reconciliation", label: "Reconciliation", Icon: IconReconcile },
];

export function Nav({ horizontal = false }: { horizontal?: boolean }) {
  const path = usePathname();
  return (
    <nav className={horizontal ? "flex gap-1 overflow-x-auto" : "flex flex-col gap-0.5"}>
      {LINKS.map(({ href, label, Icon }) => {
        const active = href === "/" ? path === "/" : path.startsWith(href);
        return (
          <Link
            key={href}
            href={href}
            aria-current={active ? "page" : undefined}
            className={`flex items-center gap-2.5 whitespace-nowrap rounded-lg px-3 py-2 text-sm transition-colors ${
              active ? "bg-zinc-900 font-medium text-white" : "text-zinc-600 hover:bg-zinc-100 hover:text-zinc-900"
            }`}
          >
            <Icon className={active ? "text-white" : "text-zinc-400"} />
            {label}
          </Link>
        );
      })}
    </nav>
  );
}
