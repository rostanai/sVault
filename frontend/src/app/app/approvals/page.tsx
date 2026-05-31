import { createClient } from "@/lib/supabase/server";
import ApprovalsClient from "./approvals-client";

export default async function ApprovalsPage() {
  const supabase = await createClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();

  const token = session?.access_token ?? "";
  return <ApprovalsClient token={token} />;
}
