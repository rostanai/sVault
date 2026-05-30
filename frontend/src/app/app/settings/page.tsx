import { createClient } from "@/lib/supabase/server";
import { getMe } from "@/lib/api";
import SettingsClient from "./settings-client";

export default async function SettingsPage() {
  const supabase = await createClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();

  const token = session?.access_token ?? "";

  // Fetch the caller's role so the client can show/hide management controls.
  let role = "viewer";
  if (token) {
    try {
      const me = await getMe(token);
      role = me.role ?? "viewer";
    } catch {
      // Non-fatal — fall back to viewer (no management controls shown).
    }
  }

  return <SettingsClient token={token} currentUserRole={role} />;
}
