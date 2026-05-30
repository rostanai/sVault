import { redirect } from "next/navigation";

// This route group has been moved to /app — redirect for any cached links
export default function OldDashboardRedirect() {
  redirect("/app");
}
