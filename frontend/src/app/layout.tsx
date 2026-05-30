import type { Metadata } from "next";
import { Analytics } from "@vercel/analytics/next";
import { SpeedInsights } from "@vercel/speed-insights/next";
import "./globals.css";

export const metadata: Metadata = {
  title: "sVault — Never miss an insurance renewal",
  description:
    "Corporate insurance portfolio & renewal management. Dashboard, document vault, and multi-channel renewal alerts (WhatsApp, SMS, Email, Telegram).",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-white text-zinc-900 dark:bg-zinc-950 dark:text-zinc-100">
        {children}
        <Analytics />
        <SpeedInsights />
      </body>
    </html>
  );
}
