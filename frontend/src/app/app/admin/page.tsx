import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import { getMe } from "@/lib/api";
import AdminClient from "./admin-client";

export default async function AdminPage() {
  const supabase = await createClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();

  const token = session?.access_token ?? "";

  let isSuper = false;
  try {
    isSuper = (await getMe(token)).is_super_admin;
  } catch {
    // getMe failed — treat as non-super-admin
  }

  if (!isSuper) redirect("/app");

  return <AdminClient token={token} />;
}
