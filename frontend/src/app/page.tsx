import type { Metadata } from "next";
import { MarketingNavbar } from "@/components/marketing/navbar";
import { HeroSection } from "@/components/marketing/hero";
import { ProblemSection } from "@/components/marketing/problem";
import { FeaturesSection } from "@/components/marketing/features";
import { HowItWorksSection } from "@/components/marketing/how-it-works";
import { AlertsHighlightSection } from "@/components/marketing/alerts-highlight";
import { SecuritySection } from "@/components/marketing/security";
import { PricingSection } from "@/components/marketing/pricing";
import { FaqSection } from "@/components/marketing/faq";
import { FinalCtaSection } from "@/components/marketing/final-cta";
import { MarketingFooter } from "@/components/marketing/footer";

export const metadata: Metadata = {
  title: "sVault — Never miss an insurance renewal again",
  description:
    "Corporate insurance portfolio & renewal management for India. Unified policy vault, multi-channel renewal alerts (WhatsApp, SMS, Email, Telegram), and AI-powered document search. 14-day free trial, no card required.",
  openGraph: {
    title: "sVault — Never miss an insurance renewal again",
    description:
      "Replace scattered spreadsheets with a unified insurance policy vault and multi-channel renewal alerts. Built for India's corporate teams.",
    type: "website",
  },
};

export default function HomePage() {
  return (
    <>
      <MarketingNavbar />
      <main id="main-content">
        <HeroSection />
        <ProblemSection />
        <FeaturesSection />
        <HowItWorksSection />
        <AlertsHighlightSection />
        <SecuritySection />
        <PricingSection />
        <FaqSection />
        <FinalCtaSection />
      </main>
      <MarketingFooter />
    </>
  );
}
