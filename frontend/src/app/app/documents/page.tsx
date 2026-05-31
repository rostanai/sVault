import { createClient } from "@/lib/supabase/server";
import DocumentsClient from "./documents-client";

export default async function DocumentsPage() {
  const supabase = await createClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();

  const token = session?.access_token ?? "";
  return <DocumentsClient token={token} />;
}
