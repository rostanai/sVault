"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { postOnboard } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { toast } from "sonner";
import { Shield } from "lucide-react";

export default function OnboardingPage() {
  const router = useRouter();
  const [companyName, setCompanyName] = useState("");
  const [fullName, setFullName] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!companyName.trim()) return;

    // Import lazily so createBrowserClient doesn't run at module evaluation
    const { createClient } = await import("@/lib/supabase/client");
    const supabase = createClient();

    setLoading(true);
    try {
      const {
        data: { session },
      } = await supabase.auth.getSession();

      if (!session?.access_token) {
        toast.error("Session expired. Please sign in again.");
        router.push("/login");
        return;
      }

      await postOnboard(session.access_token, {
        company_name: companyName.trim(),
        full_name: fullName.trim() || undefined,
      });

      // Refresh session so the new tenant claims appear in the JWT
      await supabase.auth.refreshSession();

      toast.success("Workspace created! Redirecting…");
      router.push("/app");
    } catch {
      // AppError toast is handled by the API client
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-zinc-50 p-4 dark:bg-zinc-950">
      <div className="w-full max-w-sm space-y-6">
        {/* Brand */}
        <div className="flex flex-col items-center gap-2">
          <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-brand-600 text-white">
            <Shield className="h-6 w-6" />
          </div>
          <h1 className="text-2xl font-bold tracking-tight">sVault</h1>
          <p className="text-sm text-zinc-500 dark:text-zinc-400">
            Set up your insurance workspace
          </p>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>Create your workspace</CardTitle>
            <CardDescription>
              You&#39;ll get 14 days free — no card required.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="space-y-1.5">
                <Label htmlFor="companyName">Company name</Label>
                <Input
                  id="companyName"
                  placeholder="Acme Industries Pvt. Ltd."
                  value={companyName}
                  onChange={(e) => setCompanyName(e.target.value)}
                  disabled={loading}
                  required
                  autoFocus
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="fullName">
                  Your name{" "}
                  <span className="text-zinc-400 font-normal">(optional)</span>
                </Label>
                <Input
                  id="fullName"
                  placeholder="Rahul Sharma"
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  disabled={loading}
                />
              </div>
              <Button type="submit" className="w-full" disabled={loading}>
                {loading ? "Setting up…" : "Create workspace"}
              </Button>
            </form>
          </CardContent>
        </Card>
      </div>
    </main>
  );
}
