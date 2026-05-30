import { Settings } from "lucide-react";

export default function SettingsPage() {
  return (
    <div className="flex flex-col items-center justify-center py-24 text-center">
      <Settings className="mb-3 h-10 w-10 text-zinc-300" />
      <h2 className="text-xl font-semibold">Settings</h2>
      <p className="mt-2 max-w-sm text-sm text-zinc-500">
        User and organization settings are coming in a future milestone.
      </p>
    </div>
  );
}
