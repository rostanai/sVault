import { createClient } from "@/lib/supabase/server";
import ClaimDetailClient from "./claim-detail-client";

interface Props {
  params: Promise<{ id: string }>;
}

export default async function ClaimDetailPage({ params }: Props) {
  const { id } = await params;
  const supabase = await createClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();

  const token = session?.access_token ?? "";
  return <ClaimDetailClient id={id} token={token} />;
}
