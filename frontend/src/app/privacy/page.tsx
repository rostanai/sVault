import type { Metadata } from "next";
import Link from "next/link";
import { MarketingNavbar } from "@/components/marketing/navbar";
import { MarketingFooter } from "@/components/marketing/footer";

export const metadata: Metadata = {
  title: "Privacy Policy — sVault",
  description: "sVault Privacy Policy — DPDP-aligned data handling practices.",
};

export default function PrivacyPage() {
  return (
    <>
      <MarketingNavbar />
      <main className="mx-auto max-w-3xl px-4 py-16 sm:px-6">
        <h1 className="text-3xl font-bold tracking-tight text-zinc-900 dark:text-white">
          Privacy Policy
        </h1>
        <p className="mt-2 text-sm text-zinc-500">
          Last updated: 30 May 2026 &middot; Effective: 30 May 2026
        </p>

        <div className="prose prose-zinc dark:prose-invert mt-8 max-w-none">
          <p>
            sVault (&quot;we&quot;, &quot;us&quot;, &quot;our&quot;) is committed
            to protecting your personal data in accordance with the Digital
            Personal Data Protection Act, 2023 (&quot;DPDP Act&quot;) and
            applicable Indian law.
          </p>

          <h2>1. Data we collect</h2>
          <p>
            We collect the information you provide when you create an account
            (name, email, company name), insurance policy data you enter, and
            documents you upload. We also collect usage logs for security and
            compliance purposes.
          </p>

          <h2>2. How we use your data</h2>
          <p>
            We use your data to provide the sVault service: storing and
            managing your insurance portfolio, sending renewal alerts, and
            generating AI-powered document search results. We do not sell your
            data to third parties.
          </p>

          <h2>3. Data storage and residency</h2>
          <p>
            Your data is stored on Supabase&apos;s India-region infrastructure.
            All data is encrypted at rest (AES-256) and in transit (TLS 1.3).
          </p>

          <h2>4. Data retention</h2>
          <p>
            We retain your data for as long as your account is active. On
            account deletion, data is purged within 30 days, except where
            retention is required by law. Audit logs are retained for 1 year.
          </p>

          <h2>5. Your rights (DPDP Act)</h2>
          <p>
            You have the right to access, correct, and erase your personal data.
            To exercise these rights, contact us at{" "}
            <a href="mailto:privacy@svault.in">privacy@svault.in</a>.
          </p>

          <h2>6. Data Fiduciary</h2>
          <p>
            RST Global is the Data Fiduciary under the DPDP Act for data
            processed through the sVault platform. Our Grievance Officer can be
            reached at <a href="mailto:privacy@svault.in">privacy@svault.in</a>.
          </p>

          <h2>7. Cookies</h2>
          <p>
            We use essential session cookies for authentication and optional
            analytics cookies (Vercel Analytics). You may opt out of analytics
            cookies at any time.
          </p>

          <h2>8. Changes to this policy</h2>
          <p>
            We will notify you of material changes by email or in-app notice at
            least 14 days before they take effect.
          </p>

          <p className="mt-8">
            For questions, contact us at{" "}
            <a href="mailto:privacy@svault.in">privacy@svault.in</a>.
          </p>
        </div>

        <div className="mt-12 flex gap-4 text-sm">
          <Link href="/terms" className="text-brand-600 hover:underline">
            Terms of Service
          </Link>
          <Link href="/refund" className="text-brand-600 hover:underline">
            Refund &amp; Cancellation
          </Link>
        </div>
      </main>
      <MarketingFooter />
    </>
  );
}
