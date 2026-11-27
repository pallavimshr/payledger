// Proxies the API's sample report so the browser can download it from the dashboard.
import { API_URL } from "@/lib/api";

export async function GET() {
  const res = await fetch(`${API_URL}/reconciliations/sample-report`, { cache: "no-store" });
  return new Response(await res.text(), {
    status: res.status,
    headers: {
      "Content-Type": "text/csv",
      "Content-Disposition": 'attachment; filename="razorpay_settlement_sample.csv"',
    },
  });
}
