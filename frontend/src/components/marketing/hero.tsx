import Link from "next/link";
import { Button } from "@/components/ui/button";
import { ArrowRight, ShieldCheck, Building2, Users } from "lucide-react";

export function HeroSection() {
  return (
    <section
      className="relative overflow-hidden bg-white dark:bg-zinc-950"
      aria-labelledby="hero-heading"
    >
      {/* Gradient background */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_80%_60%_at_50%_-10%,oklch(0.87_0.10_255/0.20),transparent)]"
      />

      <div className="relative mx-auto max-w-6xl px-4 pb-20 pt-20 sm:px-6 sm:pb-28 sm:pt-24 lg:pt-32">
        <div className="mx-auto max-w-3xl text-center">
          {/* Eyebrow badge */}
          <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-brand-200 bg-brand-50 px-4 py-1.5 text-xs font-semibold text-brand-700 dark:border-brand-800 dark:bg-brand-950/60 dark:text-brand-300">
            <ShieldCheck className="h-3.5 w-3.5" aria-hidden="true" />
            Corporate insurance renewal management
          </div>

          {/* Headline */}
          <h1
            id="hero-heading"
            className="text-4xl font-extrabold tracking-tight text-zinc-900 dark:text-white sm:text-5xl lg:text-6xl"
          >
            Never miss an insurance
            <br />
            <span className="bg-gradient-to-r from-brand-600 to-brand-400 bg-clip-text text-transparent">
              renewal again.
            </span>
          </h1>

          {/* Subtext */}
          <p className="mx-auto mt-6 max-w-xl text-lg text-zinc-600 dark:text-zinc-400">
            sVault replaces scattered spreadsheets with a unified policy vault,
            multi-channel renewal alerts, and AI-powered document search —
            built for India&#39;s corporate insurance teams.
          </p>

          {/* CTAs */}
          <div className="mt-10 flex flex-col items-center gap-3 sm:flex-row sm:justify-center">
            <Button size="lg" className="w-full sm:w-auto" asChild>
              <Link href="/login">
                Start free trial
                <ArrowRight className="ml-2 h-4 w-4" aria-hidden="true" />
              </Link>
            </Button>
            <Button size="lg" variant="outline" className="w-full sm:w-auto" asChild>
              <Link href="#how-it-works">See how it works</Link>
            </Button>
          </div>

          {/* Trust strip */}
          <p className="mt-6 text-sm text-zinc-400">
            14-day free trial &middot; No credit card required &middot; Cancel anytime
          </p>
        </div>

        {/* Social proof logos row */}
        <div className="mt-16 flex flex-wrap items-center justify-center gap-8 opacity-50 grayscale">
          {[
            { icon: Building2, label: "Manufacturing" },
            { icon: Building2, label: "Logistics" },
            { icon: Users, label: "Finance teams" },
            { icon: Building2, label: "Multi-entity groups" },
          ].map(({ icon: Icon, label }) => (
            <div
              key={label}
              className="flex items-center gap-2 text-sm font-medium text-zinc-500 dark:text-zinc-400"
            >
              <Icon className="h-4 w-4" aria-hidden="true" />
              {label}
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
