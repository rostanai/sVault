import { createClient } from "@/lib/supabase/server";
import AskClient from "./ask-client";

export default async function AskPage() {
  const supabase = await createClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();

  const token = session?.access_token ?? "";
  return <AskClient token={token} />;
}
