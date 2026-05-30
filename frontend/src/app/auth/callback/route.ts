import { NextResponse } from "next/server";
import { createClient } from "@/lib/supabase/server";
import { getMe } from "@/lib/api";

export async function GET(request: Request) {
  const { searchParams, origin } = new URL(request.url);
  const code = searchParams.get("code");
  const next = searchParams.get("next") ?? "/app";

  if (code) {
    const supabase = await createClient();
    const { error } = await supabase.auth.exchangeCodeForSession(code);

    if (!error) {
      // Determine if the user needs onboarding (no tenant_id yet)
      const {
        data: { session },
      } = await supabase.auth.getSession();

      if (session?.access_token) {
        try {
          const me = await getMe(session.access_token);
          if (!me.tenant_id) {
            return NextResponse.redirect(`${origin}/onboarding`);
          }
        } catch {
          // If /auth/me fails, send to onboarding as a safe default
          return NextResponse.redirect(`${origin}/onboarding`);
        }
      }

      return NextResponse.redirect(`${origin}${next}`);
    }
  }

  // Something went wrong — redirect to login with an error hint
  return NextResponse.redirect(`${origin}/login?error=auth_callback_failed`);
}
