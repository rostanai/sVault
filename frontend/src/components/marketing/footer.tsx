import Link from "next/link";
import { Logo } from "./logo";

const footerLinks = {
  Product: [
    { label: "Features", href: "#features" },
    { label: "How it works", href: "#how-it-works" },
    { label: "Pricing", href: "#pricing" },
    { label: "Security", href: "#security" },
  ],
  Company: [
    { label: "About", href: "#" },
    { label: "Contact", href: "mailto:hello@svault.in" },
    { label: "Blog", href: "#" },
  ],
  Legal: [
    { label: "Privacy Policy", href: "/privacy" },
    { label: "Terms of Service", href: "/terms" },
    { label: "Refund & Cancellation", href: "/refund" },
  ],
};

export function MarketingFooter() {
  return (
    <footer
      className="border-t border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-950"
      aria-label="Site footer"
    >
      <div className="mx-auto max-w-6xl px-4 py-12 sm:px-6">
        <div className="grid gap-8 sm:grid-cols-2 lg:grid-cols-5">
          {/* Brand column */}
          <div className="lg:col-span-2">
            <Logo />
            <p className="mt-3 max-w-xs text-sm text-zinc-500 dark:text-zinc-400">
              Corporate insurance portfolio &amp; renewal management. Built for
              India&#39;s corporate finance teams.
            </p>
            <p className="mt-4 text-xs text-zinc-400">
              GST-compliant billing &middot; DPDP-aligned &middot; India data residency
            </p>
          </div>

          {/* Nav columns */}
          {Object.entries(footerLinks).map(([group, links]) => (
            <div key={group}>
              <p className="mb-3 text-xs font-semibold uppercase tracking-widest text-zinc-500">
                {group}
              </p>
              <ul className="space-y-2">
                {links.map((link) => (
                  <li key={link.label}>
                    <Link
                      href={link.href}
                      className="text-sm text-zinc-600 transition-colors hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-zinc-100"
                    >
                      {link.label}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        <div className="mt-10 flex flex-col items-center justify-between gap-4 border-t border-zinc-100 pt-8 dark:border-zinc-800 sm:flex-row">
          <p className="text-xs text-zinc-400">
            &copy; {new Date().getFullYear()} sVault. All rights reserved. A product of RST Global.
          </p>
          <p className="text-xs text-zinc-400">
            Made with care in India &middot;{" "}
            <Link href="/privacy" className="hover:underline">
              Privacy
            </Link>{" "}
            &middot;{" "}
            <Link href="/terms" className="hover:underline">
              Terms
            </Link>
          </p>
        </div>
      </div>
    </footer>
  );
}
