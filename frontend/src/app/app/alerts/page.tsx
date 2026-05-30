import { Bell } from "lucide-react";

export default function AlertsPage() {
  return (
    <div className="flex flex-col items-center justify-center py-24 text-center">
      <Bell className="mb-3 h-10 w-10 text-zinc-300" />
      <h2 className="text-xl font-semibold">Renewal Alerts</h2>
      <p className="mt-2 max-w-sm text-sm text-zinc-500">
        Alert configuration and notification logs are coming in the next
        milestone (M4 alert engine).
      </p>
    </div>
  );
}
