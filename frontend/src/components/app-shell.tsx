"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { cn, formatDate } from "@/lib/utils";
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
  Building2,
  Bell,
  CreditCard,
  Settings,
  Shield,
  Sparkles,
  CheckSquare,
  FileBarChart,
  Menu,
  X,
  LogOut,
  User,
  Zap,
  ShieldCheck,
  Paperclip,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { toast } from "sonner";
import {
  getNotifications,
  type NotificationFeed,
  type NotificationItem,
} from "@/lib/api";

interface NavItem {
  label: string;
  href: string;
  icon: React.ElementType;
}

const navItems: NavItem[] = [
  { label: "Dashboard", href: "/app", icon: LayoutDashboard },
  { label: "Policies", href: "/app/policies", icon: FileText },
  { label: "Documents", href: "/app/documents", icon: Paperclip },
  { label: "Providers", href: "/app/providers", icon: Building2 },
  { label: "Ask sVault", href: "/app/ask", icon: Sparkles },
  { label: "Approvals", href: "/app/approvals", icon: CheckSquare },
  { label: "Alerts", href: "/app/alerts", icon: Bell },
  { label: "Reports", href: "/app/reports", icon: FileBarChart },
  { label: "Billing", href: "/app/billing", icon: CreditCard },
  { label: "Settings", href: "/app/settings", icon: Settings },
];

interface AppShellProps {
  children: React.ReactNode;
  email: string;
  name: string;
  avatarUrl?: string;
  planName?: string;
  subscriptionStatus?: string;
  trialDaysLeft?: number | null;
  isSuperAdmin?: boolean;
  token?: string;
}

export default function AppShell({
  children,
  email,
  name,
  avatarUrl,
  planName = "Free",
  subscriptionStatus = "free",
  trialDaysLeft = null,
  isSuperAdmin = false,
  token = "",
}: AppShellProps) {
  const pathname = usePathname();
  const router = useRouter();
  const [sidebarOpen, setSidebarOpen] = useState(false);

  // Notification state
  const emptyFeed: NotificationFeed = { unread_count: 0, items: [] };
  const [notifFeed, setNotifFeed] = useState<NotificationFeed>(emptyFeed);

  useEffect(() => {
    if (!token) return;

    let cancelled = false;

    async function fetchFeed() {
      try {
        const feed = await getNotifications(token);
        if (!cancelled && feed) {
          setNotifFeed(feed);
        }
      } catch {
        // Degrade silently — bell shows 0/empty
      }
    }

    fetchFeed();
    const intervalId = setInterval(fetchFeed, 60_000);
    return () => {
      cancelled = true;
      clearInterval(intervalId);
    };
  }, [token]);

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

  // Map notification type to icon component
  function notifIcon(type: NotificationItem["type"]): React.ElementType {
    if (type === "alert") return Bell;
    if (type === "approval") return CheckSquare;
    return Sparkles;
  }

  // Determine plan badge variant and CTA label.
  const isTrialing = subscriptionStatus === "trialing";
  const isActive = (href: string) => {
    if (href === "/app") return pathname === "/app";
    return pathname.startsWith(href);
  };

  const planBadgeVariant: "success" | "warning" | "secondary" =
    subscriptionStatus === "active"
      ? "success"
      : subscriptionStatus === "trialing"
        ? "warning"
        : "secondary";

  const planCtaLabel =
    subscriptionStatus === "active" ? "Manage plan" : "Upgrade";

  const PlanStatusBlock = () => (
    <div className="mx-3 mb-3 mt-2 rounded-lg border border-zinc-200 bg-zinc-50 p-3 dark:border-zinc-700 dark:bg-zinc-800/60">
      <div className="flex items-center gap-2">
        <Zap
          className="h-3.5 w-3.5 shrink-0 text-brand-600 dark:text-brand-400"
          aria-hidden="true"
        />
        <span className="text-xs font-semibold text-zinc-800 dark:text-zinc-100 truncate">
          {planName}
        </span>
        <Badge
          variant={planBadgeVariant}
          className="ml-auto shrink-0 text-[10px] leading-none px-1.5 py-0.5 capitalize"
        >
          {isTrialing && trialDaysLeft != null
            ? `${trialDaysLeft}d left`
            : subscriptionStatus.replace(/_/g, " ")}
        </Badge>
      </div>
      <Link
        href="/app/billing"
        onClick={() => setSidebarOpen(false)}
        className="mt-2 block text-xs font-medium text-brand-600 hover:text-brand-700 dark:text-brand-400 dark:hover:text-brand-300 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 rounded"
        aria-label={`${planCtaLabel} — go to billing`}
      >
        {planCtaLabel} &rarr;
      </Link>
    </div>
  );

  // Build the full nav list: shared items + conditional Admin item
  const allNavItems: NavItem[] = [
    ...navItems,
    ...(isSuperAdmin
      ? [{ label: "Admin", href: "/app/admin", icon: ShieldCheck }]
      : []),
  ];

  const Sidebar = ({ mobile = false }: { mobile?: boolean }) => (
    <nav
      className={cn(
        "flex flex-col gap-1 px-3 py-4",
        mobile ? "pt-2" : "h-full"
      )}
      aria-label="Main navigation"
    >
      <div className="flex-1">
        {allNavItems.map(({ label, href, icon: Icon }) => (
          <Link
            key={href}
            href={href}
            onClick={() => setSidebarOpen(false)}
            className={cn(
              "flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors",
              isActive(href)
                ? "bg-brand-600 text-white"
                : "text-zinc-600 hover:bg-zinc-100 hover:text-zinc-900 dark:text-zinc-400 dark:hover:bg-zinc-800 dark:hover:text-zinc-100",
              // Highlight Admin link distinctly when not active
              href === "/app/admin" && !isActive(href)
                ? "border border-dashed border-brand-200 dark:border-brand-900"
                : ""
            )}
            aria-current={isActive(href) ? "page" : undefined}
          >
            <Icon className="h-4 w-4 shrink-0" />
            {label}
          </Link>
        ))}
      </div>
      <PlanStatusBlock />
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

          {/* Right-side controls */}
          <div className="flex items-center gap-1">
            {/* Notification bell */}
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button
                  variant="ghost"
                  size="icon"
                  className="relative"
                  aria-label="Notifications"
                >
                  <Bell className="h-5 w-5" />
                  {notifFeed.unread_count > 0 && (
                    <span
                      className="absolute right-1.5 top-1.5 flex h-4 w-4 items-center justify-center rounded-full bg-red-500 text-[10px] font-bold leading-none text-white"
                      aria-label={`${notifFeed.unread_count} unread`}
                    >
                      {notifFeed.unread_count > 99
                        ? "99+"
                        : notifFeed.unread_count}
                    </span>
                  )}
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-80">
                <DropdownMenuLabel className="flex items-center justify-between">
                  <span>Notifications</span>
                  {notifFeed.unread_count > 0 && (
                    <Badge variant="secondary" className="text-xs">
                      {notifFeed.unread_count} unread
                    </Badge>
                  )}
                </DropdownMenuLabel>
                <DropdownMenuSeparator />
                {notifFeed.items.length === 0 ? (
                  <div className="px-3 py-6 text-center text-sm text-zinc-500 dark:text-zinc-400">
                    You&apos;re all caught up.
                  </div>
                ) : (
                  notifFeed.items.slice(0, 8).map((item) => {
                    const NotifIcon = notifIcon(item.type);
                    return (
                      <DropdownMenuItem key={item.id} asChild>
                        <Link
                          href={item.href}
                          className="flex items-start gap-3 py-2.5"
                        >
                          <NotifIcon
                            className="mt-0.5 h-4 w-4 shrink-0 text-brand-600 dark:text-brand-400"
                            aria-hidden="true"
                          />
                          <div className="min-w-0 flex-1">
                            <p className="truncate text-sm font-medium leading-tight">
                              {item.title}
                            </p>
                            {item.subtitle && (
                              <p className="truncate text-xs text-zinc-500 dark:text-zinc-400">
                                {item.subtitle}
                              </p>
                            )}
                            <p className="mt-0.5 text-xs text-zinc-400 dark:text-zinc-500">
                              {formatDate(item.created_at)}
                            </p>
                          </div>
                        </Link>
                      </DropdownMenuItem>
                    );
                  })
                )}
                <DropdownMenuSeparator />
                <DropdownMenuItem asChild>
                  <Link
                    href="/app/alerts"
                    className="justify-center text-xs font-medium text-brand-600 hover:text-brand-700 dark:text-brand-400 dark:hover:text-brand-300"
                  >
                    View all alerts
                  </Link>
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>

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
          </div>
        </header>

        {/* Page content */}
        <main className="flex-1 overflow-y-auto p-4 lg:p-6">{children}</main>
      </div>
    </div>
  );
}
