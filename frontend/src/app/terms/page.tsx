import type { Metadata } from "next";
import Link from "next/link";
import { MarketingNavbar } from "@/components/marketing/navbar";
import { MarketingFooter } from "@/components/marketing/footer";

export const metadata: Metadata = {
  title: "Terms of Service — sVault",
  description: "sVault Terms of Service.",
};

export default function TermsPage() {
  return (
    <>
      <MarketingNavbar />
      <main className="mx-auto max-w-3xl px-4 py-16 sm:px-6">
        <h1 className="text-3xl font-bold tracking-tight text-zinc-900 dark:text-white">
          Terms of Service
        </h1>
        <p className="mt-2 text-sm text-zinc-500">
          Last updated: 30 May 2026 &middot; Effective: 30 May 2026
        </p>

        <div className="prose prose-zinc dark:prose-invert mt-8 max-w-none">
          <p>
            By accessing or using the sVault platform (&quot;Service&quot;), you
            agree to be bound by these Terms of Service. If you do not agree,
            do not use the Service.
          </p>

          <h2>1. Eligibility</h2>
          <p>
            The Service is intended for businesses and their authorized
            representatives. By registering, you confirm that you have the
            authority to bind your organization.
          </p>

          <h2>2. Subscription and payment</h2>
          <p>
            Paid subscriptions are billed monthly or annually in INR via
            Razorpay. Prices are inclusive of applicable GST. You may upgrade or
            downgrade your plan at any time; see our{" "}
            <Link href="/refund">Refund &amp; Cancellation Policy</Link> for
            details.
          </p>

          <h2>3. Free trial</h2>
          <p>
            New accounts receive a 14-day free trial with Professional plan
            access. No credit card is required during the trial. At the end of
            the trial, your account downgrades to the Free plan unless you
            subscribe.
          </p>

          <h2>4. Acceptable use</h2>
          <p>
            You agree not to use the Service to: (a) violate any law or
            regulation; (b) upload malicious code; (c) attempt to gain
            unauthorized access to the Service or other users&apos; data; (d)
            infringe intellectual property rights.
          </p>

          <h2>5. Data ownership</h2>
          <p>
            You retain all rights to the data and documents you upload. You
            grant us a limited license to store, process, and display that data
            solely to provide the Service.
          </p>

          <h2>6. Service availability</h2>
          <p>
            We aim for 99.5% uptime but do not guarantee uninterrupted service.
            Planned maintenance will be communicated in advance.
          </p>

          <h2>7. Limitation of liability</h2>
          <p>
            To the maximum extent permitted by law, sVault is not liable for
            any indirect, incidental, or consequential damages arising from use
            of the Service.
          </p>

          <h2>8. Governing law</h2>
          <p>
            These Terms are governed by the laws of India. Disputes shall be
            subject to the exclusive jurisdiction of courts in Mumbai,
            Maharashtra.
          </p>

          <h2>9. Changes to terms</h2>
          <p>
            We may update these Terms. Material changes will be notified by
            email at least 14 days before they take effect. Continued use after
            the effective date constitutes acceptance.
          </p>

          <p className="mt-8">
            Questions? Contact{" "}
            <a href="mailto:legal@svault.in">legal@svault.in</a>.
          </p>
        </div>

        <div className="mt-12 flex gap-4 text-sm">
          <Link href="/privacy" className="text-brand-600 hover:underline">
            Privacy Policy
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
