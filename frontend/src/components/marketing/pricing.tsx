import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Check } from "lucide-react";

const plans = [
  {
    name: "Free",
    price: "₹0",
    period: "forever",
    description: "For individuals and very small teams getting started.",
    features: [
      "Up to 10 policies",
      "Email alerts",
      "Document vault (1 GB)",
      "Basic dashboard",
    ],
    cta: "Get started free",
    highlight: false,
  },
  {
    name: "Starter",
    price: "₹2,499",
    period: "per month",
    description: "For SMEs managing their own insurance portfolio.",
    features: [
      "Up to 50 policies",
      "WhatsApp + SMS + Email alerts",
      "Document vault (10 GB)",
      "Analytics dashboard",
      "1 subsidiary org",
      "Priority support",
    ],
    cta: "Start free trial",
    highlight: false,
  },
  {
    name: "Professional",
    price: "₹7,499",
    period: "per month",
    description: "For multi-entity corporate groups.",
    features: [
      "Unlimited policies",
      "All channels + Telegram",
      "Document vault (100 GB)",
      "AI Ask sVault (RAG)",
      "Approval workflows",
      "5 subsidiary orgs",
      "API access",
      "Dedicated onboarding",
    ],
    cta: "Start free trial",
    highlight: true,
  },
  {
    name: "Enterprise",
    price: "Custom",
    period: "",
    description: "For large groups with custom requirements.",
    features: [
      "Unlimited everything",
      "Custom alert cadence",
      "Unlimited subsidiary orgs",
      "SSO / custom auth",
      "SLA guarantee",
      "Dedicated CSM",
      "On-premise option",
    ],
    cta: "Contact us",
    highlight: false,
  },
];

export function PricingSection() {
  return (
    <section
      id="pricing"
      className="bg-white py-20 dark:bg-zinc-950"
      aria-labelledby="pricing-heading"
    >
      <div className="mx-auto max-w-6xl px-4 sm:px-6">
        <div className="mx-auto max-w-2xl text-center">
          <p className="text-sm font-semibold uppercase tracking-widest text-brand-600">
            Pricing
          </p>
          <h2
            id="pricing-heading"
            className="mt-2 text-3xl font-bold tracking-tight text-zinc-900 dark:text-white sm:text-4xl"
          >
            Simple, transparent pricing
          </h2>
          <p className="mt-4 text-zinc-600 dark:text-zinc-400">
            All plans include a 14-day free trial. No credit card required to
            start. INR pricing inclusive of GST.
          </p>
        </div>

        <div className="mt-12 grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
          {plans.map((plan) => (
            <div
              key={plan.name}
              className={`relative flex flex-col rounded-2xl border p-6 ${
                plan.highlight
                  ? "border-brand-500 bg-brand-50 ring-2 ring-brand-500/30 dark:bg-brand-950/30"
                  : "border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900"
              }`}
            >
              {plan.highlight && (
                <div className="absolute -top-3 left-1/2 -translate-x-1/2">
                  <span className="rounded-full bg-brand-600 px-3 py-1 text-xs font-semibold text-white">
                    Most popular
                  </span>
                </div>
              )}

              <div className="mb-4">
                <p className="text-sm font-semibold text-zinc-500 dark:text-zinc-400">
                  {plan.name}
                </p>
                <div className="mt-1 flex items-baseline gap-1">
                  <span className="text-3xl font-extrabold text-zinc-900 dark:text-white">
                    {plan.price}
                  </span>
                  {plan.period && (
                    <span className="text-sm text-zinc-500">/{plan.period}</span>
                  )}
                </div>
                <p className="mt-2 text-xs text-zinc-500">{plan.description}</p>
              </div>

              <ul className="mb-6 flex-1 space-y-2">
                {plan.features.map((f) => (
                  <li key={f} className="flex items-start gap-2 text-sm">
                    <Check
                      className="mt-0.5 h-4 w-4 shrink-0 text-emerald-500"
                      aria-hidden="true"
                    />
                    <span className="text-zinc-700 dark:text-zinc-300">{f}</span>
                  </li>
                ))}
              </ul>

              <Button
                variant={plan.highlight ? "default" : "outline"}
                className="w-full"
                asChild
              >
                <Link href="/login">{plan.cta}</Link>
              </Button>
            </div>
          ))}
        </div>

        <p className="mt-8 text-center text-sm text-zinc-400">
          All prices in INR + GST. Annual billing available at 20% discount.
          Upgrade or downgrade anytime.
        </p>
      </div>
    </section>
  );
}
