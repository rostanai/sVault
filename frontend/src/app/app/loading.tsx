// Instant, JS-free skeleton streamed by Next.js while the app segment's server
// data resolves — replaces the multi-second blank screen during JS evaluation,
// dramatically improving perceived First Contentful Paint.
export default function Loading() {
  return (
    <div className="space-y-6" aria-busy="true" aria-label="Loading">
      <div className="space-y-2">
        <div className="h-8 w-48 rounded-md bg-zinc-200 dark:bg-zinc-800 animate-pulse" />
        <div className="h-4 w-64 rounded bg-zinc-100 dark:bg-zinc-800/60 animate-pulse" />
      </div>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <div
            key={i}
            className="h-28 rounded-xl border border-zinc-200 bg-zinc-100 dark:border-zinc-800 dark:bg-zinc-900 animate-pulse"
          />
        ))}
      </div>
      <div className="grid gap-4 lg:grid-cols-3">
        {Array.from({ length: 3 }).map((_, i) => (
          <div
            key={i}
            className="h-48 rounded-xl border border-zinc-200 bg-zinc-100 dark:border-zinc-800 dark:bg-zinc-900 animate-pulse"
          />
        ))}
      </div>
    </div>
  );
}
