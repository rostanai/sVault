import Link from "next/link";
import { Button } from "@/components/ui/button";
import { ArrowRight } from "lucide-react";

export function FinalCtaSection() {
  return (
    <section
      className="relative overflow-hidden bg-brand-600 py-20"
      aria-labelledby="final-cta-heading"
    >
      {/* Subtle gradient overlay */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_70%_80%_at_50%_120%,oklch(0.47_0.20_255/0.4),transparent)]"
      />

      <div className="relative mx-auto max-w-3xl px-4 text-center sm:px-6">
        <h2
          id="final-cta-heading"
          className="text-3xl font-extrabold tracking-tight text-white sm:text-4xl"
        >
          Start your 14-day free trial
        </h2>
        <p className="mt-4 text-lg text-brand-100">
          No credit card required. Import your policies in minutes. Never miss
          a renewal again.
        </p>

        <div className="mt-10 flex flex-col items-center gap-3 sm:flex-row sm:justify-center">
          <Button
            size="lg"
            className="w-full bg-white text-brand-700 hover:bg-brand-50 sm:w-auto"
            asChild
          >
            <Link href="/login">
              Get started free
              <ArrowRight className="ml-2 h-4 w-4" aria-hidden="true" />
            </Link>
          </Button>
          <Button
            size="lg"
            variant="outline"
            className="w-full border-brand-300 text-white hover:bg-brand-700 sm:w-auto"
            asChild
          >
            <Link href="mailto:hello@svault.in">Talk to sales</Link>
          </Button>
        </div>

        <p className="mt-6 text-sm text-brand-200">
          Trusted by India&#39;s corporate finance and operations teams
        </p>
      </div>
    </section>
  );
}
