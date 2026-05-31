import { createClient } from "@/lib/supabase/server";
import DeveloperClient from "./developer-client";

export default async function DeveloperPage() {
  const supabase = await createClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();

  const token = session?.access_token ?? "";
  return <DeveloperClient token={token} />;
}
