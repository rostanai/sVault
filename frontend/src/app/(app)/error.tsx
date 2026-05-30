"use client";

import { Button } from "@/components/ui/button";
import { AlertTriangle } from "lucide-react";

export default function AppError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <div className="flex flex-col items-center justify-center py-24 text-center">
      <AlertTriangle className="mb-3 h-10 w-10 text-red-400" />
      <h2 className="text-xl font-semibold">Something went wrong</h2>
      <p className="mt-2 text-sm text-zinc-500">
        {error.digest ? `Reference: ${error.digest}` : "An unexpected error occurred."}
      </p>
      <Button onClick={reset} className="mt-4" size="sm">
        Try again
      </Button>
    </div>
  );
}
