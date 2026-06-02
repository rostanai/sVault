"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import type { SupabaseClient } from "@supabase/supabase-js";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Logo } from "@/components/marketing/logo";
import { toast } from "sonner";
import { ArrowLeft, ShieldAlert } from "lucide-react";

async function getSupabase() {
  const { createClient } = await import("@/lib/supabase/client");
  return createClient();
}

const MIN_PASSWORD_LENGTH = 8;

type Status = "checking" | "ready" | "invalid";

export default function ResetPasswordForm() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const [status, setStatus] = useState<Status>("checking");
  const [loading, setLoading] = useState(false);
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);

  // Establish the recovery session: handle the ?code= exchange and/or the
  // PASSWORD_RECOVERY auth event, falling back to an existing session.
  useEffect(() => {
    let active = true;
    let unsubscribe: (() => void) | null = null;

    async function init() {
      // If Supabase redirected back with an explicit error, surface it.
      const urlError =
        searchParams.get("error_description") ?? searchParams.get("error");
      if (urlError) {
        if (active) setStatus("invalid");
        return;
      }

      const supabase: SupabaseClient = await getSupabase();

      // React to the recovery event (covers implicit/hash-fragment links).
      const {
        data: { subscription },
      } = supabase.auth.onAuthStateChange((event, session) => {
        if (!active) return;
        if (event === "PASSWORD_RECOVERY" || (session && event === "SIGNED_IN")) {
          setStatus("ready");
        }
      });
      unsubscribe = () => subscription.unsubscribe();

      // PKCE flow: exchange the ?code= for a recovery session.
      const code = searchParams.get("code");
      if (code) {
        const { error: exchangeError } =
          await supabase.auth.exchangeCodeForSession(code);
        if (!active) return;
        if (exchangeError) {
          setStatus("invalid");
          return;
        }
        setStatus("ready");
        return;
      }

      // Fallback: a recovery session may already be active.
      const {
        data: { session },
      } = await supabase.auth.getSession();
      if (!active) return;
      if (session) {
        setStatus("ready");
      } else {
        // Wait one tick for a possible PASSWORD_RECOVERY event; if still no
        // session, treat the link as invalid/expired.
        setTimeout(async () => {
          if (!active) return;
          const {
            data: { session: late },
          } = await supabase.auth.getSession();
          if (!active) return;
          setStatus((prev) =>
            prev === "ready" ? prev : late ? "ready" : "invalid"
          );
        }, 600);
      }
    }

    init();

    return () => {
      active = false;
      if (unsubscribe) unsubscribe();
    };
    // searchParams is stable per navigation; run once on mount.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);

    if (password.length < MIN_PASSWORD_LENGTH) {
      setError(`Password must be at least ${MIN_PASSWORD_LENGTH} characters.`);
      return;
    }
    if (password !== confirm) {
      setError("Passwords do not match.");
      return;
    }

    setLoading(true);
    const supabase = await getSupabase();
    try {
      const { error: updateError } = await supabase.auth.updateUser({
        password,
      });
      if (updateError) {
        toast.error(updateError.message);
      } else {
        toast.success("Password updated. You're all set.");
        router.push("/app");
      }
    } finally {
      setLoading(false);
    }
  }

  // ── Invalid / expired recovery link ────────────────────────────────
  if (status === "invalid") {
    return (
      <main className="flex min-h-screen items-center justify-center bg-zinc-50 px-4 py-10 dark:bg-zinc-950">
        <div className="w-full max-w-sm space-y-6">
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

          <div className="space-y-4">
            <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-amber-100 dark:bg-amber-950">
              <ShieldAlert className="h-6 w-6 text-amber-600 dark:text-amber-400" />
            </div>
            <div className="space-y-1">
              <p className="text-base font-semibold">Reset link expired</p>
              <p className="text-sm text-zinc-500 dark:text-zinc-400">
                This password reset link is invalid or has expired. Request a
                new one and we&apos;ll email you a fresh link.
              </p>
            </div>
            <Button asChild className="w-full">
              <Link href="/forgot-password">Request a new link</Link>
            </Button>
          </div>
        </div>
      </main>
    );
  }

  // ── Checking the recovery session ───────────────────────────────
  if (status === "checking") {
    return (
      <main className="flex min-h-screen items-center justify-center bg-zinc-50 px-4 py-10 dark:bg-zinc-950">
        <div className="w-full max-w-sm space-y-6">
          <Logo />
          <p className="text-sm text-zinc-500 dark:text-zinc-400">
            Verifying your reset link…
          </p>
        </div>
      </main>
    );
  }

  // ── Ready: new-password form ───────────────────────────────────
  return (
    <main className="flex min-h-screen items-center justify-center bg-zinc-50 px-4 py-10 dark:bg-zinc-950">
      <div className="w-full max-w-sm space-y-6">
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

        <div className="space-y-4">
          <div className="space-y-1">
            <p className="text-base font-semibold">Set a new password</p>
            <p className="text-sm text-zinc-500 dark:text-zinc-400">
              Choose a strong password you don&apos;t use anywhere else.
            </p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-3" noValidate>
            <div className="space-y-1.5">
              <Label htmlFor="new-password">New password</Label>
              <Input
                id="new-password"
                type="password"
                placeholder="8+ characters"
                autoComplete="new-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                disabled={loading}
                required
                minLength={MIN_PASSWORD_LENGTH}
                aria-invalid={error ? true : undefined}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="confirm-password">Confirm password</Label>
              <Input
                id="confirm-password"
                type="password"
                placeholder="Re-enter your password"
                autoComplete="new-password"
                value={confirm}
                onChange={(e) => setConfirm(e.target.value)}
                disabled={loading}
                required
                minLength={MIN_PASSWORD_LENGTH}
                aria-invalid={error ? true : undefined}
              />
            </div>

            {error && (
              <p role="alert" className="text-sm text-red-600 dark:text-red-400">
                {error}
              </p>
            )}

            <Button type="submit" className="w-full" disabled={loading}>
              {loading ? "Please wait…" : "Update password"}
            </Button>
          </form>
        </div>
      </div>
    </main>
  );
}
