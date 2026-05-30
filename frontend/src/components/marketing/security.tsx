import { Lock, ShieldCheck, Database, FileCheck, Eye, Clock } from "lucide-react";

const badges = [
  {
    icon: Lock,
    title: "Encryption at rest",
    desc: "All data and documents encrypted at rest using AES-256.",
    color: "text-brand-600",
    bg: "bg-brand-50 dark:bg-brand-950/40",
  },
  {
    icon: ShieldCheck,
    title: "Row-Level Security",
    desc: "Supabase RLS enforces tenant isolation at the database layer.",
    color: "text-emerald-600",
    bg: "bg-emerald-50 dark:bg-emerald-950/40",
  },
  {
    icon: Database,
    title: "India data residency",
    desc: "Data stored on Supabase's India-region infrastructure.",
    color: "text-violet-600",
    bg: "bg-violet-50 dark:bg-violet-950/40",
  },
  {
    icon: FileCheck,
    title: "DPDP-aligned",
    desc: "Designed for India's Digital Personal Data Protection Act 2023.",
    color: "text-orange-500",
    bg: "bg-orange-50 dark:bg-orange-950/40",
  },
  {
    icon: Clock,
    title: "1-year audit log",
    desc: "Every action logged with user, timestamp, and request ID.",
    color: "text-rose-600",
    bg: "bg-rose-50 dark:bg-rose-950/40",
  },
  {
    icon: Eye,
    title: "Permission-aware AI",
    desc: "RAG search is RLS-filtered — users only see documents they can access.",
    color: "text-amber-600",
    bg: "bg-amber-50 dark:bg-amber-950/40",
  },
];

export function SecuritySection() {
  return (
    <section
      id="security"
      className="bg-zinc-50 py-20 dark:bg-zinc-900"
      aria-labelledby="security-heading"
    >
      <div className="mx-auto max-w-6xl px-4 sm:px-6">
        <div className="mx-auto max-w-2xl text-center">
          <p className="text-sm font-semibold uppercase tracking-widest text-brand-600">
            Security &amp; compliance
          </p>
          <h2
            id="security-heading"
            className="mt-2 text-3xl font-bold tracking-tight text-zinc-900 dark:text-white sm:text-4xl"
          >
            Built for enterprise trust
          </h2>
          <p className="mt-4 text-zinc-600 dark:text-zinc-400">
            Insurance data is sensitive. sVault was designed from day one with
            security, compliance, and data privacy as first-class requirements.
          </p>
        </div>

        <div className="mt-12 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {badges.map((b) => (
            <div
              key={b.title}
              className="flex items-start gap-4 rounded-2xl border border-zinc-100 bg-white p-5 shadow-sm dark:border-zinc-800 dark:bg-zinc-800/60"
            >
              <div
                className={`mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-lg ${b.bg}`}
              >
                <b.icon className={`h-4 w-4 ${b.color}`} aria-hidden="true" />
              </div>
              <div>
                <p className="font-semibold text-zinc-900 dark:text-white">
                  {b.title}
                </p>
                <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
                  {b.desc}
                </p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
