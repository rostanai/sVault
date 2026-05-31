import { createClient } from "@/lib/supabase/server";
import ProviderDetailClient from "./provider-detail-client";

interface Props {
  params: Promise<{ id: string }>;
}

export default async function ProviderDetailPage({ params }: Props) {
  const { id } = await params;
  const supabase = await createClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();

  const token = session?.access_token ?? "";
  return <ProviderDetailClient id={id} token={token} />;
}
