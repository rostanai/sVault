import { Bell, MessageSquare, Mail, Phone } from "lucide-react";

const channels = [
  {
    icon: MessageSquare,
    label: "WhatsApp",
    color: "text-green-600",
    bg: "bg-green-50 dark:bg-green-950/40",
    desc: "Utility template messages",
  },
  {
    icon: Phone,
    label: "SMS",
    color: "text-blue-600",
    bg: "bg-blue-50 dark:bg-blue-950/40",
    desc: "DLT-compliant transactional",
  },
  {
    icon: Mail,
    label: "Email",
    color: "text-brand-600",
    bg: "bg-brand-50 dark:bg-brand-950/40",
    desc: "HTML + plain text",
  },
  {
    icon: Bell,
    label: "Telegram",
    color: "text-sky-600",
    bg: "bg-sky-50 dark:bg-sky-950/40",
    desc: "Bot channel",
  },
];

const cadence = [
  { days: "60", label: "days before", urgency: "bg-emerald-500" },
  { days: "30", label: "days before", urgency: "bg-yellow-400" },
  { days: "15", label: "days before", urgency: "bg-orange-400" },
  { days: "7", label: "days before", urgency: "bg-red-400" },
  { days: "1", label: "day before", urgency: "bg-red-600" },
];

export function AlertsHighlightSection() {
  return (
    <section
      className="bg-white py-20 dark:bg-zinc-950"
      aria-labelledby="alerts-heading"
    >
      <div className="mx-auto max-w-6xl px-4 sm:px-6">
        <div className="grid items-center gap-12 lg:grid-cols-2">
          {/* Left: copy */}
          <div>
            <p className="text-sm font-semibold uppercase tracking-widest text-brand-600">
              Core differentiator
            </p>
            <h2
              id="alerts-heading"
              className="mt-2 text-3xl font-bold tracking-tight text-zinc-900 dark:text-white sm:text-4xl"
            >
              Alerts across every channel, on your schedule
            </h2>
            <p className="mt-4 text-zinc-600 dark:text-zinc-400">
              sVault sends renewal alerts at the right time on every channel
              your team actually uses — WhatsApp, SMS, Email, and Telegram.
              Escalation to managers if the first alert is missed.
            </p>

            {/* Cadence timeline */}
            <div className="mt-8">
              <p className="mb-3 text-xs font-semibold uppercase tracking-widest text-zinc-500">
                Alert cadence
              </p>
              <ol className="flex flex-wrap items-center gap-2">
                {cadence.map((c, i) => (
                  <li key={c.days} className="flex items-center gap-2">
                    <span
                      className={`inline-flex h-7 w-7 items-center justify-center rounded-full text-xs font-bold text-white ${c.urgency}`}
                    >
                      {c.days}d
                    </span>
                    {i < cadence.length - 1 && (
                      <div
                        aria-hidden="true"
                        className="h-px w-4 bg-zinc-300 dark:bg-zinc-600"
                      />
                    )}
                  </li>
                ))}
              </ol>
              <p className="mt-2 text-xs text-zinc-500">
                60 &rarr; 30 &rarr; 15 &rarr; 7 &rarr; 1 day before expiry
              </p>
            </div>
          </div>

          {/* Right: channel cards */}
          <div className="grid grid-cols-2 gap-4">
            {channels.map((ch) => (
              <div
                key={ch.label}
                className="rounded-2xl border border-zinc-100 bg-zinc-50 p-5 dark:border-zinc-800 dark:bg-zinc-900"
              >
                <div
                  className={`mb-3 inline-flex h-10 w-10 items-center justify-center rounded-xl ${ch.bg}`}
                >
                  <ch.icon className={`h-5 w-5 ${ch.color}`} aria-hidden="true" />
                </div>
                <p className="font-semibold text-zinc-900 dark:text-white">
                  {ch.label}
                </p>
                <p className="mt-0.5 text-xs text-zinc-500">{ch.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
