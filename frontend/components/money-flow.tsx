import { money } from "@/lib/api";

/**
 * "Where the money went": one tall segmented bar splitting everything customers
 * paid into its four destinations. Colours are categorical slots 1-4 in fixed
 * order (validated for colour-blind separation); several are low-contrast on
 * white, so every part is also named with its amount and share in the legend.
 */
const PARTS = [
  { key: "bank", label: "Settled to bank", color: "#257de0", ink: "#ffffff" },
  { key: "held", label: "Held by gateway", color: "#f47230", ink: "#ffffff" },
  { key: "refunded", label: "Refunded to customers", color: "#00b894", ink: "#ffffff" },
  { key: "fees", label: "Gateway fees", color: "#f2a600", ink: "#0b0b0b" },
] as const;

type Key = (typeof PARTS)[number]["key"];

export function MoneyFlow({ values }: { values: Record<Key, number> }) {
  const total = PARTS.reduce((s, p) => s + values[p.key], 0);
  if (total <= 0) {
    return <p className="px-5 py-8 text-center text-sm text-zinc-400">No money has moved yet.</p>;
  }
  const share = (v: number) => (v / total) * 100;
  const pct = (v: number) => `${share(v) < 1 && v > 0 ? "<1" : Math.round(share(v))}%`;

  return (
    <div className="px-5 py-5">
      <div className="mb-4 flex items-baseline justify-between gap-4">
        <p className="text-sm text-zinc-500">Collected from customers</p>
        <p className="text-lg font-semibold tabular-nums">{money(total)}</p>
      </div>

      <div className="flex h-7 w-full gap-[2px]" role="img"
        aria-label={`Of ${money(total)} collected: ${PARTS.map((p) => `${p.label} ${money(values[p.key])} (${pct(values[p.key])})`).join(", ")}`}>
        {PARTS.filter((p) => values[p.key] > 0).map((p) => (
          <div key={p.key} title={`${p.label}: ${money(values[p.key])} (${pct(values[p.key])})`}
            className="flex min-w-[3px] items-center overflow-hidden rounded-[4px] px-2 text-xs font-medium"
            style={{ flexBasis: `${share(values[p.key])}%`, backgroundColor: p.color, color: p.ink }}>
            {share(values[p.key]) >= 9 && <span className="tabular-nums">{pct(values[p.key])}</span>}
          </div>
        ))}
      </div>

      <ul className="mt-4 grid gap-x-6 gap-y-2 text-sm sm:grid-cols-2 lg:grid-cols-4">
        {PARTS.map((p) => (
          <li key={p.key} className="flex items-start gap-2">
            <span className="mt-1 h-3 w-3 shrink-0 rounded-[3px]" style={{ backgroundColor: p.color }} aria-hidden />
            <span>
              <span className="block text-zinc-600">{p.label}</span>
              <span className="tabular-nums font-medium">{money(values[p.key])}</span>
              <span className="ml-1.5 tabular-nums text-xs text-zinc-400">{pct(values[p.key])}</span>
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
