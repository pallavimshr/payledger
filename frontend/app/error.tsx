"use client";

export default function Error({ error, reset }: { error: Error; reset: () => void }) {
  return (
    <div className="rounded-xl border border-red-200 bg-red-50 p-6">
      <p className="font-medium text-red-800">Something went wrong</p>
      <p className="mt-1 text-sm text-red-700">{error.message}</p>
      <button onClick={reset} className="mt-4 rounded-md bg-white px-3 py-1.5 text-sm ring-1 ring-red-200 hover:bg-red-100">
        Try again
      </button>
    </div>
  );
}
