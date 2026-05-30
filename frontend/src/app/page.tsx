import { getHealth } from "@/lib/api";

export default async function Home() {
  // Server component: confirms the frontend can reach the backend.
  let api = "unknown";
  try {
    const h = await getHealth();
    api = h.status;
  } catch {
    api = "unreachable";
  }

  return (
    <main className="mx-auto flex min-h-screen max-w-3xl flex-col items-center justify-center gap-6 p-8 text-center">
      <h1 className="text-4xl font-bold tracking-tight">sVault</h1>
      <p className="text-lg text-zinc-600 dark:text-zinc-400">
        Never miss an insurance renewal again.
      </p>
      <p className="text-sm text-zinc-500">
        Backend API status: <span className="font-mono">{api}</span>
      </p>
      <p className="text-xs text-zinc-400">M0 scaffold — marketing site & app land in later milestones.</p>
    </main>
  );
}
