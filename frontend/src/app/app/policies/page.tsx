import { createClient } from "@/lib/supabase/server";
import PoliciesClient from "./policies-client";

export default async function PoliciesPage() {
  const supabase = await createClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();

  const token = session?.access_token ?? "";
  return <PoliciesClient token={token} />;
}
