import { createClient } from "@/lib/supabase/server";
import NotificationsClient from "./notifications-client";

export default async function NotificationsPage() {
  const supabase = await createClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();

  const token = session?.access_token ?? "";
  return <NotificationsClient token={token} />;
}
