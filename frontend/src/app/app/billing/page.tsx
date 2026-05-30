import { createClient } from "@/lib/supabase/server";
import BillingClient from "./billing-client";

export default async function BillingPage() {
  const supabase = await createClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();

  const token = session?.access_token ?? "";
  return <BillingClient token={token} />;
}
