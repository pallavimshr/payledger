"use client";

import { useActionState, useState } from "react";

import { uploadReport, type UploadState } from "@/app/actions";

export function UploadForm() {
  const [state, action, pending] = useActionState<UploadState, FormData>(uploadReport, {});
  const [name, setName] = useState<string>();

  return (
    <form action={action} className="space-y-3">
      <label className="flex cursor-pointer flex-col items-center justify-center gap-1 rounded-xl border-2 border-dashed border-zinc-200 bg-zinc-50/50 px-6 py-8 text-center transition-colors hover:border-zinc-300 hover:bg-zinc-50">
        <span className="text-sm font-medium">{name ?? "Choose a settlement report (.csv)"}</span>
        <span className="text-xs text-zinc-400">Razorpay settlement export · max 5 MB</span>
        <input type="file" name="file" accept=".csv,text/csv" className="sr-only"
          onChange={(e) => setName(e.target.files?.[0]?.name)} />
      </label>
      {state.error && <p role="alert" className="text-sm text-red-700">{state.error}</p>}
      <button disabled={pending}
        className="w-full rounded-lg bg-zinc-900 px-4 py-2.5 text-sm font-medium text-white shadow-sm transition-colors hover:bg-zinc-700 disabled:cursor-wait disabled:bg-zinc-500">
        {pending ? "Matching rows and asking the AI…" : "Reconcile"}
      </button>
    </form>
  );
}
