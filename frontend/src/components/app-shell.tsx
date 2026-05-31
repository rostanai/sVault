"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { cn } from "@/lib/utils";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Button } from "@/components/ui/button";
import {
  LayoutDashboard,
  FileText,
  Bell,
  CreditCard,
  Settings,
  Shield,
  Sparkles,
  CheckSquare,
  Menu,
  X,
  LogOut,
  User,
} from "lucide-react";
import { toast } from "sonner";

interface NavItem {
  label: string;
  href: string;
  icon: React.ElementType;
}

const navItems: NavItem[] = [
  { label: "Dashboard", href: "/app", icon: LayoutDashboard },
  { label: "Policies", href: "/app/policies", icon: FileText },
  { label: "Ask sVault", href: "/app/ask", icon: Sparkles },
  { label: "Approvals", href: "/app/approvals", icon: CheckSquare },
  { label: "Alerts", href: "/app/alerts", icon: Bell },
  { label: "Billing", href: "/app/billing", icon: CreditCard },
  { label: "Settings", href: "/app/settings", icon: Settings },
];

interface AppShellProps {
  children: React.ReactNode;
  email: string;
  name: string;
  avatarUrl?: string;
}

export default function AppShell({
  children,
  email,
  name,
  avatarUrl,
}: AppShellProps) {
  const pathname = usePathname();
  const router = useRouter();
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const initials = name
    .split(" ")
    .map((w) => w[0])
    .slice(0, 2)
    .join("")
    .toUpperCase();

  async function handleSignOut() {
    const { createClient } = await import("@/lib/supabase/client");
    const supabase = createClient();
    await supabase.auth.signOut();
    toast.success("Signed out");
    router.push("/login");
  }

  function isActive(href: string) {
    if (href === "/app") return pathname === "/app";
    return pathname.startsWith(href);
  }

  const Sidebar = ({ mobile = false }: { mobile?: boolean }) => (
    <nav
      className={cn(
        "flex flex-col gap-1 px-3 py-4",
        mobile ? "pt-2" : "h-full"
      )}
    >
      {navItems.map(({ label, href, icon: Icon }) => (
        <Link
          key={href}
          href={href}
          onClick={() => setSidebarOpen(false)}
          className={cn(
            "flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors",
            isActive(href)
              ? "bg-brand-600 text-white"
              : "text-zinc-600 hover:bg-zinc-100 hover:text-zinc-900 dark:text-zinc-400 dark:hover:bg-zinc-800 dark:hover:text-zinc-100"
          )}
          aria-current={isActive(href) ? "page" : undefined}
        >
          <Icon className="h-4 w-4 shrink-0" />
          {label}
        </Link>
      ))}
    </nav>
  );

  return (
    <div className="flex min-h-screen bg-zinc-50 dark:bg-zinc-950">
      {/* Desktop sidebar */}
      <aside className="hidden w-60 shrink-0 flex-col border-r border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900 lg:flex">
        {/* Logo */}
        <div className="flex h-14 items-center gap-2 border-b border-zinc-100 px-5 dark:border-zinc-800">
          <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-brand-600 text-white">
            <Shield className="h-4 w-4" />
          </div>
          <span className="font-semibold tracking-tight">sVault</span>
        </div>
        <div className="flex-1 overflow-y-auto">
          <Sidebar />
        </div>
      </aside>

      {/* Mobile sidebar overlay */}
      {sidebarOpen && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div
            className="absolute inset-0 bg-black/40"
            onClick={() => setSidebarOpen(false)}
            aria-hidden="true"
          />
          <aside className="absolute left-0 top-0 flex h-full w-64 flex-col border-r border-zinc-200 bg-white shadow-xl dark:border-zinc-800 dark:bg-zinc-900">
            <div className="flex h-14 items-center justify-between border-b border-zinc-100 px-5 dark:border-zinc-800">
              <div className="flex items-center gap-2">
                <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-brand-600 text-white">
                  <Shield className="h-4 w-4" />
                </div>
                <span className="font-semibold tracking-tight">sVault</span>
              </div>
              <button
                onClick={() => setSidebarOpen(false)}
                className="rounded-md p-1 text-zinc-500 hover:bg-zinc-100 dark:hover:bg-zinc-800"
                aria-label="Close sidebar"
              >
                <X className="h-5 w-5" />
              </button>
            </div>
            <div className="flex-1 overflow-y-auto">
              <Sidebar mobile />
            </div>
          </aside>
        </div>
      )}

      {/* Main content area */}
      <div className="flex min-w-0 flex-1 flex-col">
        {/* Topbar */}
        <header className="flex h-14 items-center justify-between border-b border-zinc-200 bg-white px-4 dark:border-zinc-800 dark:bg-zinc-900 lg:px-6">
          <button
            onClick={() => setSidebarOpen(true)}
            className="rounded-md p-1.5 text-zinc-500 hover:bg-zinc-100 dark:hover:bg-zinc-800 lg:hidden"
            aria-label="Open navigation"
          >
            <Menu className="h-5 w-5" />
          </button>

          {/* Spacer for desktop */}
          <div className="hidden lg:block" />

          {/* User menu */}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                variant="ghost"
                size="sm"
                className="flex items-center gap-2 px-2"
                aria-label="User menu"
              >
                <Avatar className="h-7 w-7">
                  {avatarUrl && (
                    <AvatarImage src={avatarUrl} alt={name} />
                  )}
                  <AvatarFallback>{initials}</AvatarFallback>
                </Avatar>
                <span className="hidden max-w-[160px] truncate text-sm sm:block">
                  {name}
                </span>
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-52">
              <DropdownMenuLabel className="font-normal">
                <div className="flex flex-col space-y-1">
                  <p className="text-sm font-medium leading-none">{name}</p>
                  <p className="truncate text-xs text-zinc-500 dark:text-zinc-400">
                    {email}
                  </p>
                </div>
              </DropdownMenuLabel>
              <DropdownMenuSeparator />
              <DropdownMenuItem asChild>
                <Link href="/app/settings" className="cursor-pointer">
                  <User className="mr-2 h-4 w-4" />
                  Settings
                </Link>
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem
                onClick={handleSignOut}
                className="cursor-pointer text-red-600 focus:text-red-600 dark:text-red-400"
              >
                <LogOut className="mr-2 h-4 w-4" />
                Sign out
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </header>

        {/* Page content */}
        <main className="flex-1 overflow-y-auto p-4 lg:p-6">{children}</main>
      </div>
    </div>
  );
}
