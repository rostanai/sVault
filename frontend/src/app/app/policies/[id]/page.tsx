import { createClient } from "@/lib/supabase/server";
import PolicyDetailClient from "./policy-detail-client";

interface Props {
  params: Promise<{ id: string }>;
}

export default async function PolicyDetailPage({ params }: Props) {
  const { id } = await params;
  const supabase = await createClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();

  const token = session?.access_token ?? "";
  return <PolicyDetailClient id={id} token={token} />;
}
