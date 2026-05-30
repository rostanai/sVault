import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

// ── Formatting helpers ────────────────────────────────────────────────────────

const inrFormatter = new Intl.NumberFormat("en-IN", {
  style: "currency",
  currency: "INR",
  maximumFractionDigits: 0,
});

export function formatINR(value: string | number | null | undefined): string {
  if (value == null) return "—";
  const num = typeof value === "string" ? parseFloat(value) : value;
  if (isNaN(num)) return "—";
  return inrFormatter.format(num);
}

export function formatDate(
  value: string | null | undefined,
  opts?: Intl.DateTimeFormatOptions
): string {
  if (!value) return "—";
  const d = new Date(value);
  if (isNaN(d.getTime())) return "—";
  return d.toLocaleDateString("en-IN", opts ?? { day: "2-digit", month: "short", year: "numeric" });
}

export function daysLeftVariant(
  days: number | null | undefined
): "destructive" | "warning" | "success" {
  if (days == null) return "success";
  if (days < 7) return "destructive";
  if (days < 30) return "warning";
  return "success";
}

export function categorylabel(cat: string): string {
  const map: Record<string, string> = {
    vehicle: "Vehicle",
    machinery: "Machinery",
    plant: "Plant",
    factory_property: "Factory / Property",
    employees_group_health: "Employees (GHI)",
    key_person: "Key Person",
    stock_raw_material: "Stock – RM",
    stock_finished_goods: "Stock – FG",
    other: "Other",
  };
  return map[cat] ?? cat;
}

export function statusLabel(s: string): string {
  const map: Record<string, string> = {
    draft: "Draft",
    pending_approval: "Pending Approval",
    active: "Active",
    expiring: "Expiring",
    lapsed: "Lapsed",
    renewed: "Renewed",
    cancelled: "Cancelled",
  };
  return map[s] ?? s;
}
