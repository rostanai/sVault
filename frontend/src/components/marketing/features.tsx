import {
  Bell,
  FileText,
  LayoutDashboard,
  MessageSquare,
  GitBranch,
  Building2,
} from "lucide-react";

const features = [
  {
    icon: Bell,
    title: "Multi-channel renewal alerts",
    description:
      "Automated reminders via WhatsApp, SMS, Email, and Telegram at 60, 30, 15, 7, and 1 day before expiry. Escalate to managers if ignored.",
    color: "text-orange-500",
    bg: "bg-orange-50 dark:bg-orange-950/40",
  },
  {
    icon: FileText,
    title: "Policy & document vault",
    description:
      "Store every policy document, endorsement, and certificate in one secure place. Signed URLs, full audit trail, encrypted at rest.",
    color: "text-brand-600",
    bg: "bg-brand-50 dark:bg-brand-950/40",
  },
  {
    icon: LayoutDashboard,
    title: "Dashboard & analytics",
    description:
      "Portfolio-wide view: total coverage, expiring soon, premium spend, by-category breakdown. Know your exposure at a glance.",
    color: "text-violet-600",
    bg: "bg-violet-50 dark:bg-violet-950/40",
  },
  {
    icon: MessageSquare,
    title: 'AI "Ask sVault"',
    description:
      "Ask natural language questions over your policy documents. What is the claim limit for Plant 3? Answer in seconds, not days.",
    color: "text-emerald-600",
    bg: "bg-emerald-50 dark:bg-emerald-950/40",
  },
  {
    icon: GitBranch,
    title: "Approval workflows",
    description:
      "Configurable policy actions routed by role. Owners submit, managers approve, with self-approval where permitted. Full audit log.",
    color: "text-rose-600",
    bg: "bg-rose-50 dark:bg-rose-950/40",
  },
  {
    icon: Building2,
    title: "Multi-company / subsidiaries",
    description:
      "Parent-company admins see a consolidated group dashboard. Each subsidiary stays isolated. Perfect for holding companies and groups.",
    color: "text-amber-600",
    bg: "bg-amber-50 dark:bg-amber-950/40",
  },
];

export function FeaturesSection() {
  return (
    <section
      id="features"
      className="bg-white py-20 dark:bg-zinc-950"
      aria-labelledby="features-heading"
    >
      <div className="mx-auto max-w-6xl px-4 sm:px-6">
        <div className="mx-auto max-w-2xl text-center">
          <p className="text-sm font-semibold uppercase tracking-widest text-brand-600">
            Features
          </p>
          <h2
            id="features-heading"
            className="mt-2 text-3xl font-bold tracking-tight text-zinc-900 dark:text-white sm:text-4xl"
          >
            Everything your team needs
          </h2>
          <p className="mt-4 text-zinc-600 dark:text-zinc-400">
            Built specifically for India&#39;s corporate insurance operations —
            from single-entity SMEs to multi-subsidiary groups.
          </p>
        </div>

        <div className="mt-14 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {features.map((feat) => (
            <article
              key={feat.title}
              className="group rounded-2xl border border-zinc-100 bg-zinc-50 p-6 transition-shadow hover:shadow-md dark:border-zinc-800 dark:bg-zinc-900"
            >
              <div
                className={`mb-4 inline-flex h-10 w-10 items-center justify-center rounded-xl ${feat.bg}`}
              >
                <feat.icon
                  className={`h-5 w-5 ${feat.color}`}
                  aria-hidden="true"
                />
              </div>
              <h3 className="mb-2 text-base font-semibold text-zinc-900 dark:text-white">
                {feat.title}
              </h3>
              <p className="text-sm leading-relaxed text-zinc-600 dark:text-zinc-400">
                {feat.description}
              </p>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}
