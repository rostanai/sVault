"use client";

import * as React from "react";
import { cn } from "@/lib/utils";

// Dependency-free checkbox with a shadcn-compatible API (checked / onCheckedChange).
// Uses a native <input type="checkbox"> styled via Tailwind accent-color.

export interface CheckboxProps
  extends Omit<
    React.InputHTMLAttributes<HTMLInputElement>,
    "type" | "onChange" | "checked"
  > {
  checked?: boolean;
  onCheckedChange?: (checked: boolean) => void;
}

const Checkbox = React.forwardRef<HTMLInputElement, CheckboxProps>(
  ({ className, checked, onCheckedChange, ...props }, ref) => (
    <input
      ref={ref}
      type="checkbox"
      data-slot="checkbox"
      checked={checked}
      onChange={(e) => onCheckedChange?.(e.target.checked)}
      className={cn(
        "h-4 w-4 shrink-0 cursor-pointer rounded-sm border border-zinc-300 accent-brand-600",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-600 focus-visible:ring-offset-1",
        "disabled:cursor-not-allowed disabled:opacity-50",
        "dark:border-zinc-600",
        className
      )}
      {...props}
    />
  )
);
Checkbox.displayName = "Checkbox";

export { Checkbox };
