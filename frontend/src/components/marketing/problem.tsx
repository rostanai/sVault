import { X } from "lucide-react";

const painPoints = [
  "Renewal dates buried in multiple Excel files — easy to miss.",
  "Policy documents scattered across email threads and shared drives.",
  "No audit trail when a policy lapses — only discovered after a claim.",
  "Manual follow-ups with brokers eat hours every month.",
  "Multiple subsidiaries, zero consolidated view.",
  "No alerts until after the expiry date.",
];

export function ProblemSection() {
  return (
    <section
      className="bg-zinc-50 py-20 dark:bg-zinc-900"
      aria-labelledby="problem-heading"
    >
      <div className="mx-auto max-w-6xl px-4 sm:px-6">
        <div className="mx-auto max-w-2xl text-center">
          <p className="text-sm font-semibold uppercase tracking-widest text-brand-600">
            The problem
          </p>
          <h2
            id="problem-heading"
            className="mt-2 text-3xl font-bold tracking-tight text-zinc-900 dark:text-white sm:text-4xl"
          >
            Insurance management is still stuck in spreadsheets
          </h2>
          <p className="mt-4 text-zinc-600 dark:text-zinc-400">
            Most Indian corporate finance teams manage policies in Excel. The
            result? Missed renewals, lapsed coverage, and last-minute scrambles
            that expose the business to risk.
          </p>
        </div>

        <ul className="mt-12 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {painPoints.map((point) => (
            <li
              key={point}
              className="flex items-start gap-3 rounded-xl border border-red-100 bg-white p-4 shadow-sm dark:border-red-900/40 dark:bg-zinc-800/60"
            >
              <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-red-100 dark:bg-red-900/40">
                <X className="h-3 w-3 text-red-600 dark:text-red-400" aria-hidden="true" />
              </span>
              <p className="text-sm text-zinc-700 dark:text-zinc-300">{point}</p>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
