import { api } from "@/lib/api";

/** Live indicator in the sidebar: is the FastAPI backend reachable? */
export async function ApiStatus() {
  const ok = await api.health();
  return (
    <div className="flex items-center gap-2 rounded-lg border border-zinc-200 px-3 py-2 text-xs text-zinc-500">
      <span className={`h-2 w-2 rounded-full ${ok ? "bg-good" : "bg-critical"}`} aria-hidden />
      {ok ? "API online" : "API offline: run make dev"}
    </div>
  );
}
