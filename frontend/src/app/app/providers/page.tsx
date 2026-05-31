import { createClient } from "@/lib/supabase/server";
import ProvidersClient from "./providers-client";

export default async function ProvidersPage() {
  const supabase = await createClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();

  const token = session?.access_token ?? "";
  return <ProvidersClient token={token} />;
}
