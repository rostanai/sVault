"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Logo } from "@/components/marketing/logo";
import { toast } from "sonner";
import { ArrowLeft, Shield, Bell, FileText, Sparkles } from "lucide-react";

async function getSupabase() {
  const { createClient } = await import("@/lib/supabase/client");
  return createClient();
}

// ── Value props for the left panel ──────────────────────────────────────────
const bullets = [
  {
    icon: Bell,
    text: "Multi-channel renewal alerts via WhatsApp, Email and SMS",
  },
  {
    icon: FileText,
    text: "Secure document vault with signed-URL storage",
  },
  {
    icon: Sparkles,
    text: "AI-powered search across all your policy documents",
  },
];

// ── Google SVG logo ───────────────────────────────────────────────
function GoogleIcon() {
  return (
    <svg viewBox="0 0 24 24" className="h-4 w-4" aria-hidden="true">
      <path
        fill="#4285F4"
        d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
      />
      <path
        fill="#34A853"
        d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
      />
      <path
        fill="#FBBC05"
        d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l3.66-2.84z"
      />
      <path
        fill="#EA4335"
        d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
      />
    </svg>
  );
}

// ── Divider ─────────────────────────────────────────────────────
function OrDivider() {
  return (
    <div className="relative my-4">
      <div className="absolute inset-0 flex items-center">
        <span className="w-full border-t border-zinc-200 dark:border-zinc-700" />
      </div>
      <div className="relative flex justify-center text-xs uppercase">
        <span className="bg-white px-2 text-zinc-400 dark:bg-zinc-900 dark:text-zinc-500">
          or
        </span>
      </div>
    </div>
  );
}

// ── Main component ───────────────────────────────────────────────
export default function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const callbackError = searchParams.get("error");

  const [loading, setLoading] = useState(false);
  // Track email/password state per tab independently.
  const [signInEmail, setSignInEmail] = useState("");
  const [signInPassword, setSignInPassword] = useState("");
  const [signUpEmail, setSignUpEmail] = useState("");
  const [signUpPassword, setSignUpPassword] = useState("");

  async function handleGoogle() {
    setLoading(true);
    const supabase = await getSupabase();
    const { error } = await supabase.auth.signInWithOAuth({
      provider: "google",
      options: {
        redirectTo: `${window.location.origin}/auth/callback`,
      },
    });
    if (error) {
      toast.error(error.message);
      setLoading(false);
    }
    // If no error, the browser navigates away — no need to reset loading.
  }

  async function handleSignIn(e: React.FormEvent) {
    e.preventDefault();
    if (!signInEmail || !signInPassword) return;
    setLoading(true);
    const supabase = await getSupabase();
    try {
      const { error } = await supabase.auth.signInWithPassword({
        email: signInEmail,
        password: signInPassword,
      });
      if (error) {
        toast.error(error.message);
      } else {
        router.push("/auth/callback");
      }
    } finally {
      setLoading(false);
    }
  }

  async function handleSignUp(e: React.FormEvent) {
    e.preventDefault();
    if (!signUpEmail || !signUpPassword) return;
    setLoading(true);
    const supabase = await getSupabase();
    try {
      const { error } = await supabase.auth.signUp({
        email: signUpEmail,
        password: signUpPassword,
        options: {
          emailRedirectTo: `${window.location.origin}/auth/callback`,
        },
      });
      if (error) {
        toast.error(error.message);
      } else {
        toast.success("Check your email for a confirmation link.");
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="flex min-h-screen">
      {/* ── Left panel (brand) ── hidden on mobile, visible lg+ ────────────── */}
      <div
        className="hidden lg:flex lg:w-1/2 flex-col justify-between p-10 xl:p-14"
        style={{
          background:
            "linear-gradient(135deg, oklch(0.55 0.20 255) 0%, oklch(0.40 0.18 255) 100%)",
        }}
        aria-hidden="true"
      >
        {/* Brand wordmark */}
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-white/15 backdrop-blur-sm">
            <Shield className="h-5 w-5 text-white" />
          </div>
          <span className="text-xl font-bold tracking-tight text-white">
            sVault
          </span>
        </div>

        {/* Tagline + bullets */}
        <div className="space-y-8">
          <div className="space-y-3">
            <h1 className="text-3xl font-bold leading-tight text-white xl:text-4xl">
              Never miss an insurance renewal again.
            </h1>
            <p className="text-base text-white/70 leading-relaxed">
              The corporate insurance portfolio and renewal management system
              built for Indian businesses.
            </p>
          </div>
          <ul className="space-y-4">
            {bullets.map(({ icon: Icon, text }) => (
              <li key={text} className="flex items-start gap-3">
                <div className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-white/20">
                  <Icon className="h-3.5 w-3.5 text-white" />
                </div>
                <p className="text-sm text-white/85 leading-relaxed">{text}</p>
              </li>
            ))}
          </ul>
        </div>

        {/* Footer note */}
        <p className="text-xs text-white/40">
          Trusted by corporate treasury and risk teams across India.
        </p>
      </div>

      {/* ── Right panel (auth) ───────────────────────────────────── */}
      <div className="flex w-full flex-col items-center justify-center bg-zinc-50 px-4 py-10 dark:bg-zinc-950 lg:w-1/2 lg:px-12 xl:px-20">
        <div className="w-full max-w-sm space-y-6">
          {/* Logo + back link */}
          <div className="flex items-center justify-between">
            <Logo />
            <Link
              href="/"
              className="flex items-center gap-1 text-xs text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-100 transition-colors"
            >
              <ArrowLeft className="h-3.5 w-3.5" />
              Back to home
            </Link>
          </div>

          {/* Error from OAuth callback */}
          {callbackError && (
            <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-800 dark:bg-red-950 dark:text-red-400">
              Sign-in failed. Please try again.
            </div>
          )}

          {/* Tabs: Sign in / Create account */}
          <Tabs defaultValue="signin" className="w-full">
            <TabsList className="w-full">
              <TabsTrigger value="signin" className="flex-1">
                Sign in
              </TabsTrigger>
              <TabsTrigger value="signup" className="flex-1">
                Create account
              </TabsTrigger>
            </TabsList>

            {/* ── Sign in tab ────────────────────────────────── */}
            <TabsContent value="signin">
              <div className="mt-4 space-y-4">
                <div className="space-y-1">
                  <p className="text-base font-semibold">Welcome back</p>
                  <p className="text-sm text-zinc-500 dark:text-zinc-400">
                    Sign in to your sVault account.
                  </p>
                </div>

                <Button
                  variant="outline"
                  className="w-full gap-2"
                  onClick={handleGoogle}
                  disabled={loading}
                  type="button"
                >
                  <GoogleIcon />
                  Continue with Google
                </Button>

                <OrDivider />

                <form onSubmit={handleSignIn} className="space-y-3">
                  <div className="space-y-1.5">
                    <Label htmlFor="signin-email">Email</Label>
                    <Input
                      id="signin-email"
                      type="email"
                      placeholder="you@company.com"
                      autoComplete="email"
                      value={signInEmail}
                      onChange={(e) => setSignInEmail(e.target.value)}
                      disabled={loading}
                      required
                    />
                  </div>
                  <div className="space-y-1.5">
                    <div className="flex items-center justify-between">
                      <Label htmlFor="signin-password">Password</Label>
                      <Link
                        href="/forgot-password"
                        className="text-xs text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-100 transition-colors"
                      >
                        Forgot password?
                      </Link>
                    </div>
                    <Input
                      id="signin-password"
                      type="password"
                      placeholder="••••••••"
                      autoComplete="current-password"
                      value={signInPassword}
                      onChange={(e) => setSignInPassword(e.target.value)}
                      disabled={loading}
                      required
                    />
                  </div>
                  <Button
                    type="submit"
                    className="w-full"
                    disabled={loading}
                  >
                    {loading ? "Please wait…" : "Sign in"}
                  </Button>
                </form>
              </div>
            </TabsContent>

            {/* ── Sign up tab ────────────────────────────────── */}
            <TabsContent value="signup">
              <div className="mt-4 space-y-4">
                <div className="space-y-1">
                  <p className="text-base font-semibold">Start your free trial</p>
                  <p className="text-sm text-zinc-500 dark:text-zinc-400">
                    14 days free, no credit card required.
                  </p>
                </div>

                <Button
                  variant="outline"
                  className="w-full gap-2"
                  onClick={handleGoogle}
                  disabled={loading}
                  type="button"
                >
                  <GoogleIcon />
                  Continue with Google
                </Button>

                <OrDivider />

                <form onSubmit={handleSignUp} className="space-y-3">
                  <div className="space-y-1.5">
                    <Label htmlFor="signup-email">Email</Label>
                    <Input
                      id="signup-email"
                      type="email"
                      placeholder="you@company.com"
                      autoComplete="email"
                      value={signUpEmail}
                      onChange={(e) => setSignUpEmail(e.target.value)}
                      disabled={loading}
                      required
                    />
                  </div>
                  <div className="space-y-1.5">
                    <Label htmlFor="signup-password">Password</Label>
                    <Input
                      id="signup-password"
                      type="password"
                      placeholder="8+ characters"
                      autoComplete="new-password"
                      value={signUpPassword}
                      onChange={(e) => setSignUpPassword(e.target.value)}
                      disabled={loading}
                      required
                      minLength={8}
                    />
                  </div>
                  <Button
                    type="submit"
                    className="w-full"
                    disabled={loading}
                  >
                    {loading ? "Please wait…" : "Create account"}
                  </Button>
                </form>
              </div>
            </TabsContent>
          </Tabs>

          <p className="text-center text-xs text-zinc-400">
            By continuing you agree to our{" "}
            <Link
              href="/terms"
              className="underline hover:text-zinc-700 dark:hover:text-zinc-200"
            >
              Terms
            </Link>{" "}
            &amp;{" "}
            <Link
              href="/privacy"
              className="underline hover:text-zinc-700 dark:hover:text-zinc-200"
            >
              Privacy Policy
            </Link>
            .
          </p>
        </div>
      </div>
    </main>
  );
}
