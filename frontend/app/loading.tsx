// Shown instantly while a page's server data loads (React Suspense).
function Block({ className }: { className: string }) {
  return <div className={`animate-pulse rounded-xl bg-zinc-200/70 ${className}`} />;
}

export default function Loading() {
  return (
    <div aria-busy="true" aria-label="Loading">
      <Block className="mb-2 h-6 w-40" />
      <Block className="mb-8 h-4 w-64" />
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        {[0, 1, 2, 3].map((i) => <Block key={i} className="h-28" />)}
      </div>
      <Block className="mt-6 h-40" />
      <Block className="mt-6 h-64" />
    </div>
  );
}
