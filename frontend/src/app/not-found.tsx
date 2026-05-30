import Link from "next/link";

export default function NotFound() {
  return (
    <main className="mx-auto flex min-h-screen max-w-md flex-col items-center justify-center gap-4 p-8 text-center">
      <h2 className="text-2xl font-semibold">Page not found</h2>
      <Link href="/" className="text-sm text-brand-600 underline">
        Go home
      </Link>
    </main>
  );
}
