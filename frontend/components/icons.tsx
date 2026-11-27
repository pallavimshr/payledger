// Small stroke icons (24x24 grid). Decorative: always paired with a text label.
import type { SVGProps } from "react";

const base = (p: SVGProps<SVGSVGElement>) => ({
  width: 18, height: 18, viewBox: "0 0 24 24", fill: "none", stroke: "currentColor",
  strokeWidth: 1.75, strokeLinecap: "round" as const, strokeLinejoin: "round" as const,
  "aria-hidden": true, ...p,
});

export const IconOverview = (p: SVGProps<SVGSVGElement>) => (
  <svg {...base(p)}><rect x="3" y="3" width="7" height="9" rx="1.5" /><rect x="14" y="3" width="7" height="5" rx="1.5" /><rect x="14" y="12" width="7" height="9" rx="1.5" /><rect x="3" y="16" width="7" height="5" rx="1.5" /></svg>
);
export const IconOrders = (p: SVGProps<SVGSVGElement>) => (
  <svg {...base(p)}><path d="M6 3h12v18l-3-2-3 2-3-2-3 2z" /><path d="M9 8h6M9 12h6M9 16h3" /></svg>
);
export const IconLedger = (p: SVGProps<SVGSVGElement>) => (
  <svg {...base(p)}><path d="M4 5a2 2 0 0 1 2-2h13v16H6a2 2 0 0 0-2 2z" /><path d="M4 19V5M9 7h6M9 11h6" /></svg>
);
export const IconWebhook = (p: SVGProps<SVGSVGElement>) => (
  <svg {...base(p)}><path d="M13 2 4 14h7l-1 8 9-12h-7z" /></svg>
);
export const IconReconcile = (p: SVGProps<SVGSVGElement>) => (
  <svg {...base(p)}><path d="M4 7h11M4 7l3-3M4 7l3 3" /><path d="M20 17H9m11 0-3-3m3 3-3 3" /></svg>
);
export const IconSparkle = (p: SVGProps<SVGSVGElement>) => (
  <svg {...base(p)}><path d="M12 3v4M12 17v4M3 12h4M17 12h4M6 6l2.5 2.5M15.5 15.5 18 18M6 18l2.5-2.5M15.5 8.5 18 6" /></svg>
);
export const IconSearch = (p: SVGProps<SVGSVGElement>) => (
  <svg {...base(p)}><circle cx="11" cy="11" r="7" /><path d="m20 20-3.5-3.5" /></svg>
);
export const IconChevron = (p: SVGProps<SVGSVGElement>) => (
  <svg {...base(p)}><path d="m9 6 6 6-6 6" /></svg>
);

/** Logo: two balanced bars, a debit and a credit of equal height. */
export const Logo = () => (
  <span className="grid h-8 w-8 place-items-center rounded-lg bg-zinc-900" aria-hidden>
    <svg width="16" height="16" viewBox="0 0 16 16"><rect x="2" y="3" width="5" height="10" rx="1.5" fill="#fff" /><rect x="9" y="3" width="5" height="10" rx="1.5" fill="#fff" fillOpacity=".55" /></svg>
  </span>
);
