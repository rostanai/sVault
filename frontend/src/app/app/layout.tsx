import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import AppShell from "@/components/app-shell";

export default async function AppLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) {
    redirect("/login");
  }

  const email = user.email ?? "";
  const name =
    (user.user_metadata?.full_name as string | undefined) ??
    email.split("@")[0] ??
    "User";
  const avatarUrl = user.user_metadata?.avatar_url as string | undefined;

  return (
    <AppShell email={email} name={name} avatarUrl={avatarUrl}>
      {children}
    </AppShell>
  );
}
