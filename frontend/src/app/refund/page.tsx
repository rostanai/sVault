import type { Metadata } from "next";
import Link from "next/link";
import { MarketingNavbar } from "@/components/marketing/navbar";
import { MarketingFooter } from "@/components/marketing/footer";

export const metadata: Metadata = {
  title: "Refund & Cancellation Policy — sVault",
  description:
    "sVault Refund and Cancellation Policy — required for Razorpay payment gateway onboarding.",
};

export default function RefundPage() {
  return (
    <>
      <MarketingNavbar />
      <main className="mx-auto max-w-3xl px-4 py-16 sm:px-6">
        <h1 className="text-3xl font-bold tracking-tight text-zinc-900 dark:text-white">
          Refund &amp; Cancellation Policy
        </h1>
        <p className="mt-2 text-sm text-zinc-500">
          Last updated: 30 May 2026 &middot; Effective: 30 May 2026
        </p>

        <div className="prose prose-zinc dark:prose-invert mt-8 max-w-none">
          <p>
            This policy governs refunds and cancellations for paid subscriptions
            to the sVault platform. All amounts are in Indian Rupees (INR) and
            inclusive of GST.
          </p>

          <h2>1. Free trial</h2>
          <p>
            All new accounts receive a 14-day free trial. No payment is charged
            during the trial period. You may cancel at any time during the trial
            without any obligation.
          </p>

          <h2>2. Cancellation</h2>
          <p>
            You may cancel your paid subscription at any time from the Billing
            section of your account. Cancellation takes effect at the end of
            your current billing period. You retain access to paid features
            until then.
          </p>

          <h2>3. Refunds — monthly plans</h2>
          <p>
            Monthly subscriptions are non-refundable for the current billing
            period. If you cancel mid-period, you will not be charged for the
            next period, but no pro-rated refund is issued for the unused
            portion of the current period.
          </p>

          <h2>4. Refunds — annual plans</h2>
          <p>
            Annual subscriptions cancelled within 7 days of purchase are
            eligible for a full refund. Cancellations after 7 days are
            non-refundable for the remaining balance. No pro-rated refunds are
            provided for annual plans cancelled mid-year.
          </p>

          <h2>5. Refunds — failed payments</h2>
          <p>
            If a payment fails and you are incorrectly charged, contact us
            within 14 days at{" "}
            <a href="mailto:billing@svault.in">billing@svault.in</a>. We will
            investigate and issue a refund if a duplicate or erroneous charge is
            confirmed, typically within 5–7 business days to your original
            payment method.
          </p>

          <h2>6. Downgrade</h2>
          <p>
            Downgrades take effect at the start of the next billing period. No
            refund is issued for the difference in the current period.
          </p>

          <h2>7. How to request a refund</h2>
          <p>
            Email <a href="mailto:billing@svault.in">billing@svault.in</a> with
            your account email, the date of charge, and a brief reason. We
            respond within 2 business days.
          </p>

          <h2>8. Razorpay payment processing</h2>
          <p>
            Payments are processed securely by Razorpay. For payment-related
            disputes, you may also contact Razorpay support. Our Razorpay
            merchant ID is available on your invoice.
          </p>
        </div>

        <div className="mt-12 flex gap-4 text-sm">
          <Link href="/privacy" className="text-brand-600 hover:underline">
            Privacy Policy
          </Link>
          <Link href="/terms" className="text-brand-600 hover:underline">
            Terms of Service
          </Link>
        </div>
      </main>
      <MarketingFooter />
    </>
  );
}
