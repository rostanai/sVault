"use client";

// Route-level error boundary (per docs/ERROR_HANDLING.md). No white screen.
export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <main className="mx-auto flex min-h-screen max-w-md flex-col items-center justify-center gap-4 p-8 text-center">
      <h2 className="text-2xl font-semibold">Something went wrong</h2>
      <p className="text-sm text-zinc-500">
        Please try again. If it keeps happening, contact support
        {error.digest ? (
          <>
            {" "}
            with reference <span className="font-mono">{error.digest}</span>
          </>
        ) : null}
        .
      </p>
      <button
        onClick={reset}
        className="rounded-md bg-brand-600 px-4 py-2 text-sm font-medium text-white"
      >
        Try again
      </button>
    </main>
  );
}
