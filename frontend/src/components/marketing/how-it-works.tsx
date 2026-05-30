import { Upload, Bell, ShieldCheck } from "lucide-react";

const steps = [
  {
    step: "01",
    icon: Upload,
    title: "Import from Excel",
    description:
      "Paste your existing policy register or add policies one by one. Set expiry dates, sum insured, premiums, and attach documents. Up and running in minutes.",
    color: "text-brand-600",
    bg: "bg-brand-50 dark:bg-brand-950/40",
  },
  {
    step: "02",
    icon: Bell,
    title: "Get alerts automatically",
    description:
      "sVault sends renewal reminders on WhatsApp, SMS, Email, and Telegram at 60, 30, 15, 7, and 1 day before expiry. No manual tracking needed.",
    color: "text-orange-500",
    bg: "bg-orange-50 dark:bg-orange-950/40",
  },
  {
    step: "03",
    icon: ShieldCheck,
    title: "Stay covered — always",
    description:
      "Renew on time, upload the new policy, and the cycle continues automatically. No gaps. No missed renewals. Complete audit trail for compliance.",
    color: "text-emerald-600",
    bg: "bg-emerald-50 dark:bg-emerald-950/40",
  },
];

export function HowItWorksSection() {
  return (
    <section
      id="how-it-works"
      className="bg-zinc-50 py-20 dark:bg-zinc-900"
      aria-labelledby="how-heading"
    >
      <div className="mx-auto max-w-6xl px-4 sm:px-6">
        <div className="mx-auto max-w-2xl text-center">
          <p className="text-sm font-semibold uppercase tracking-widest text-brand-600">
            How it works
          </p>
          <h2
            id="how-heading"
            className="mt-2 text-3xl font-bold tracking-tight text-zinc-900 dark:text-white sm:text-4xl"
          >
            Set up in minutes. Protected forever.
          </h2>
        </div>

        <div className="mt-14 grid gap-8 md:grid-cols-3">
          {steps.map((step, i) => (
            <div key={step.step} className="relative flex flex-col items-start">
              {/* Connector line */}
              {i < steps.length - 1 && (
                <div
                  aria-hidden="true"
                  className="absolute left-[calc(100%_-_2rem)] top-5 hidden h-px w-full bg-zinc-200 dark:bg-zinc-700 md:block"
                />
              )}

              <div
                className={`mb-4 inline-flex h-12 w-12 items-center justify-center rounded-xl ${step.bg}`}
              >
                <step.icon
                  className={`h-6 w-6 ${step.color}`}
                  aria-hidden="true"
                />
              </div>

              <div className="mb-2 text-xs font-bold uppercase tracking-widest text-zinc-400">
                Step {step.step}
              </div>
              <h3 className="mb-2 text-lg font-semibold text-zinc-900 dark:text-white">
                {step.title}
              </h3>
              <p className="text-sm leading-relaxed text-zinc-600 dark:text-zinc-400">
                {step.description}
              </p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
