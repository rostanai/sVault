import { createClient } from "@/lib/supabase/server";
import DashboardClient from "./dashboard-client";
import { getDashboard } from "@/lib/api";

export default async function DashboardPage() {
  const supabase = await createClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();

  const token = session?.access_token ?? "";

  // Prefetch the dashboard on the server (in parallel with the layout's own
  // data) so the client renders real content immediately instead of fetching
  // after hydration — removes the ~1.5s LCP gap and the skeleton flash.
  // Best-effort: any failure falls back to the client fetch path.
  const initialData = token
    ? await getDashboard(token).catch(() => null)
    : null;

  return <DashboardClient token={token} initialData={initialData} />;
}
