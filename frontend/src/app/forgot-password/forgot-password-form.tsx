"use client";

import { useState } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Logo } from "@/components/marketing/logo";
import { toast } from "sonner";
import { ArrowLeft, MailCheck } from "lucide-react";

async function getSupabase() {
  const { createClient } = await import("@/lib/supabase/client");
  return createClient();
}

export default function ForgotPasswordForm() {
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [sent, setSent] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!email) return;
    setLoading(true);
    const supabase = await getSupabase();
    try {
      const { error } = await supabase.auth.resetPasswordForEmail(email, {
        redirectTo: `${window.location.origin}/reset-password`,
      });
      if (error) {
        toast.error(error.message);
      } else {
        setSent(true);
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-zinc-50 px-4 py-10 dark:bg-zinc-950">
      <div className="w-full max-w-sm space-y-6">
        {/* Logo + back link */}
        <div className="flex items-center justify-between">
          <Logo />
          <Link
            href="/login"
            className="flex items-center gap-1 text-xs text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-100 transition-colors"
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            Back to sign in
          </Link>
        </div>

        {sent ? (
          <div className="space-y-4">
            <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-green-100 dark:bg-green-950">
              <MailCheck className="h-6 w-6 text-green-600 dark:text-green-400" />
            </div>
            <div className="space-y-1">
              <p className="text-base font-semibold">Check your email</p>
              <p className="text-sm text-zinc-500 dark:text-zinc-400">
                If an account exists for{" "}
                <span className="font-medium text-zinc-700 dark:text-zinc-300">
                  {email}
                </span>
                , we&apos;ve sent a link to reset your password. The link
                expires soon, so use it promptly.
              </p>
            </div>
            <Button
              variant="outline"
              className="w-full"
              type="button"
              onClick={() => setSent(false)}
            >
              Use a different email
            </Button>
            <p className="text-center text-sm text-zinc-500 dark:text-zinc-400">
              Back to{" "}
              <Link
                href="/login"
                className="font-medium text-zinc-900 underline hover:text-zinc-700 dark:text-zinc-100 dark:hover:text-zinc-300"
              >
                sign in
              </Link>
            </p>
          </div>
        ) : (
          <div className="space-y-4">
            <div className="space-y-1">
              <p className="text-base font-semibold">Forgot your password?</p>
              <p className="text-sm text-zinc-500 dark:text-zinc-400">
                Enter the email linked to your sVault account and we&apos;ll
                send you a link to reset it.
              </p>
            </div>

            <form onSubmit={handleSubmit} className="space-y-3">
              <div className="space-y-1.5">
                <Label htmlFor="forgot-email">Email</Label>
                <Input
                  id="forgot-email"
                  type="email"
                  placeholder="you@company.com"
                  autoComplete="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  disabled={loading}
                  required
                />
              </div>
              <Button type="submit" className="w-full" disabled={loading}>
                {loading ? "Please wait…" : "Send reset link"}
              </Button>
            </form>

            <p className="text-center text-sm text-zinc-500 dark:text-zinc-400">
              Remembered it?{" "}
              <Link
                href="/login"
                className="font-medium text-zinc-900 underline hover:text-zinc-700 dark:text-zinc-100 dark:hover:text-zinc-300"
              >
                Sign in
              </Link>
            </p>
          </div>
        )}
      </div>
    </main>
  );
}
