import { createClient } from "@/lib/supabase/server";
import ClaimsClient from "./claims-client";

export default async function ClaimsPage() {
  const supabase = await createClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();

  const token = session?.access_token ?? "";
  return <ClaimsClient token={token} />;
}
