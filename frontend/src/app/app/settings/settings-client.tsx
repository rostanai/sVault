"use client";

import { useEffect, useState } from "react";
import {
  getUsers,
  updateUser,
  getInvitations,
  createInvitation,
  downloadDataExport,
  sendDigestNow,
  type ProfileRead,
  type InvitationRead,
} from "@/lib/api";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Switch } from "@/components/ui/switch";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Users,
  UserPlus,
  AlertTriangle,
  Copy,
  Check,
  Clock,
  Loader2,
  Download,
  Mail,
  ShieldCheck,
} from "lucide-react";
import { toast } from "sonner";
import { formatDate } from "@/lib/utils";

const ROLES = ["admin", "manager", "owner", "viewer"] as const;
type TenantRole = (typeof ROLES)[number];

interface Props {
  token: string;
  currentUserRole: string;
}

export default function SettingsClient({ token, currentUserRole }: Props) {
  const isAdmin = currentUserRole === "admin";

  const [users, setUsers] = useState<ProfileRead[]>([]);
  const [invitations, setInvitations] = useState<InvitationRead[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  function loadData() {
    if (!token) {
      setError("No active session.");
      setLoading(false);
      return;
    }
    setLoading(true);
    Promise.all([
      getUsers(token),
      getInvitations(token).catch(() => [] as InvitationRead[]),
    ])
      .then(([usersRes, invsRes]) => {
        setUsers(usersRes);
        setInvitations(invsRes);
      })
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    loadData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  if (loading) return <TeamSkeleton />;
  if (error) return <ErrorState message={error} />;

  return (
    <div className="space-y-8 max-w-4xl mx-auto">
      <div>
        <h2 className="text-2xl font-bold tracking-tight">Team</h2>
        <p className="text-sm text-zinc-500 dark:text-zinc-400">
          Manage members and pending invitations.
          {!isAdmin && (
            <span className="ml-1 text-zinc-400">
              Contact your admin to make changes.
            </span>
          )}
        </p>
      </div>

      {/* Members table */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between gap-4 pb-3">
          <div>
            <CardTitle className="text-sm font-semibold">Members</CardTitle>
            <CardDescription className="text-xs mt-0.5">
              The company creator is the Admin.
            </CardDescription>
          </div>
          {isAdmin && (
            <InviteDialog
              token={token}
              onInvited={() => loadData()}
            />
          )}
        </CardHeader>
        <CardContent className="p-0">
          {users.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-10 text-center">
              <Users className="mb-2 h-8 w-8 text-zinc-300" />
              <p className="text-sm text-zinc-500">No members yet.</p>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name / Email</TableHead>
                  <TableHead>Role</TableHead>
                  <TableHead>Active</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {users.map((u) => (
                  <UserRow
                    key={u.id}
                    user={u}
                    isAdmin={isAdmin}
                    token={token}
                    onUpdated={() => loadData()}
                  />
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {/* Pending invitations */}
      {(isAdmin || invitations.length > 0) && (
        <Card>
          <CardHeader>
            <CardTitle className="text-sm font-semibold">
              Pending Invitations
            </CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            {invitations.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-8 text-center">
                <Clock className="mb-2 h-7 w-7 text-zinc-300" />
                <p className="text-sm text-zinc-500">
                  No pending invitations.
                </p>
              </div>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Email</TableHead>
                    <TableHead>Role</TableHead>
                    <TableHead>Expires</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {invitations.map((inv) => (
                    <TableRow key={inv.id}>
                      <TableCell className="font-medium">{inv.email}</TableCell>
                      <TableCell>
                        <RoleBadge role={inv.role} />
                      </TableCell>
                      <TableCell className="text-zinc-500 text-sm">
                        {formatDate(inv.expires_at)}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>
      )}

      {/* Your data & privacy */}
      <YourDataCard token={token} />
    </div>
  );
}

// ── UserRow ───────────────────────────────────────────────
function UserRow({
  user,
  isAdmin,
  token,
  onUpdated,
}: {
  user: ProfileRead;
  isAdmin: boolean;
  token: string;
  onUpdated: () => void;
}) {
  const [savingRole, setSavingRole] = useState(false);
  const [savingActive, setSavingActive] = useState(false);

  async function handleRoleChange(newRole: string) {
    if (newRole === user.role) return;
    setSavingRole(true);
    try {
      await updateUser(token, user.id, { role: newRole });
      toast.success(`Role updated to "${newRole}".`);
      onUpdated();
    } catch {
      // apiFetch already showed a toast.
    } finally {
      setSavingRole(false);
    }
  }

  async function handleActiveToggle(checked: boolean) {
    setSavingActive(true);
    try {
      await updateUser(token, user.id, {
        role: user.role,
        is_active: checked,
      });
      toast.success(checked ? "User reactivated." : "User deactivated.");
      onUpdated();
    } catch {
      // apiFetch already showed a toast.
    } finally {
      setSavingActive(false);
    }
  }

  const displayName = user.full_name ?? user.email.split("@")[0];

  return (
    <TableRow className={!user.is_active ? "opacity-50" : undefined}>
      <TableCell>
        <p className="font-medium text-sm">{displayName}</p>
        <p className="text-xs text-zinc-500">{user.email}</p>
      </TableCell>
      <TableCell>
        {isAdmin ? (
          <div className="flex items-center gap-2">
            <Select
              value={user.role}
              onValueChange={handleRoleChange}
              disabled={savingRole}
            >
              <SelectTrigger className="h-8 w-32 text-xs">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {ROLES.map((r) => (
                  <SelectItem key={r} value={r} className="text-xs capitalize">
                    {r}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {savingRole && (
              <Loader2 className="h-3.5 w-3.5 animate-spin text-zinc-400" />
            )}
          </div>
        ) : (
          <RoleBadge role={user.role} />
        )}
      </TableCell>
      <TableCell>
        {isAdmin ? (
          <div className="flex items-center gap-2">
            <Switch
              checked={user.is_active}
              onCheckedChange={handleActiveToggle}
              disabled={savingActive}
              aria-label={`Toggle active for ${user.email}`}
            />
            {savingActive && (
              <Loader2 className="h-3.5 w-3.5 animate-spin text-zinc-400" />
            )}
          </div>
        ) : (
          <Badge variant={user.is_active ? "success" : "secondary"}>
            {user.is_active ? "Active" : "Inactive"}
          </Badge>
        )}
      </TableCell>
    </TableRow>
  );
}

// ── InviteDialog ──────────────────────────────────────────
function InviteDialog({
  token,
  onInvited,
}: {
  token: string;
  onInvited: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<TenantRole>("viewer");
  const [loading, setLoading] = useState(false);
  const [inviteLink, setInviteLink] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  function reset() {
    setEmail("");
    setRole("viewer");
    setInviteLink(null);
    setCopied(false);
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!email) return;
    setLoading(true);
    try {
      const inv = await createInvitation(token, { email, role });
      const invToken = inv.token ?? inv.id;
      const link = `${window.location.origin}/login?invite=${invToken}`;
      setInviteLink(link);
      toast.success(`Invitation sent to ${email}.`);
      onInvited();
    } catch {
      // apiFetch already showed a toast.
    } finally {
      setLoading(false);
    }
  }

  function handleCopy() {
    if (!inviteLink) return;
    navigator.clipboard
      .writeText(inviteLink)
      .then(() => {
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
      })
      .catch(() => toast.error("Failed to copy to clipboard."));
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(v) => {
        setOpen(v);
        if (!v) reset();
      }}
    >
      <DialogTrigger asChild>
        <Button size="sm">
          <UserPlus className="mr-1.5 h-4 w-4" />
          Invite member
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Invite a team member</DialogTitle>
          <DialogDescription>
            They will receive an invitation link to join your organisation.
          </DialogDescription>
        </DialogHeader>

        {inviteLink ? (
          <div className="space-y-4 py-2">
            <p className="text-sm text-zinc-600 dark:text-zinc-400">
              Share this link with <strong>{email}</strong>:
            </p>
            <div className="flex items-center gap-2">
              <Input
                readOnly
                value={inviteLink}
                className="flex-1 text-xs"
                onFocus={(e) => e.target.select()}
              />
              <Button
                type="button"
                size="sm"
                variant="outline"
                onClick={handleCopy}
                aria-label="Copy invite link"
              >
                {copied ? (
                  <Check className="h-4 w-4 text-emerald-500" />
                ) : (
                  <Copy className="h-4 w-4" />
                )}
              </Button>
            </div>
            <DialogFooter>
              <Button
                variant="outline"
                onClick={() => {
                  setOpen(false);
                  reset();
                }}
              >
                Done
              </Button>
            </DialogFooter>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-4 py-2">
            <div className="space-y-1.5">
              <Label htmlFor="invite-email">Email address</Label>
              <Input
                id="invite-email"
                type="email"
                placeholder="colleague@company.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                disabled={loading}
                required
                autoComplete="off"
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="invite-role">Role</Label>
              <Select
                value={role}
                onValueChange={(v) => setRole(v as TenantRole)}
                disabled={loading}
              >
                <SelectTrigger id="invite-role">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {ROLES.map((r) => (
                    <SelectItem key={r} value={r} className="capitalize">
                      {r}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <DialogFooter>
              <Button
                type="button"
                variant="outline"
                onClick={() => setOpen(false)}
                disabled={loading}
              >
                Cancel
              </Button>
              <Button type="submit" disabled={loading || !email}>
                {loading ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Sending…
                  </>
                ) : (
                  "Send invitation"
                )}
              </Button>
            </DialogFooter>
          </form>
        )}
      </DialogContent>
    </Dialog>
  );
}

// ── YourDataCard ──────────────────────────────────────────
interface DigestResult {
  sent: boolean;
  recipient: string | null;
  policies: number;
}

function YourDataCard({ token }: { token: string }) {
  const [exportLoading, setExportLoading] = useState(false);
  const [digestLoading, setDigestLoading] = useState(false);

  async function handleExport() {
    setExportLoading(true);
    try {
      await downloadDataExport(token);
      toast.success("Your data export has downloaded.");
    } catch {
      // downloadDataExport (via apiFetch) already toasted the error.
    } finally {
      setExportLoading(false);
    }
  }

  async function handleDigest() {
    setDigestLoading(true);
    try {
      const res = (await sendDigestNow(token)) as DigestResult;
      if (res.sent) {
        toast.success(
          `Digest sent${res.recipient ? " to " + res.recipient : ""} — ${res.policies} upcoming renewal(s).`
        );
      } else {
        toast.info("No email on file to send to.");
      }
    } catch {
      // sendDigestNow (via apiFetch) already toasted the error.
    } finally {
      setDigestLoading(false);
    }
  }

  return (
    <Card>
      <CardHeader className="flex flex-row items-center gap-3 pb-3">
        <ShieldCheck
          className="h-5 w-5 text-zinc-500 dark:text-zinc-400 shrink-0"
          aria-hidden="true"
        />
        <div>
          <CardTitle className="text-sm font-semibold">
            Your data &amp; privacy
          </CardTitle>
          <CardDescription className="text-xs mt-0.5">
            DPDP data-portability and communication preferences.
          </CardDescription>
        </div>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Export your data */}
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div className="space-y-1">
            <p className="text-sm font-medium leading-none">Export your data</p>
            <p className="text-xs text-zinc-500 dark:text-zinc-400 max-w-sm">
              Download a JSON copy of all your organisation&apos;s data —
              policies, providers, documents metadata, approvals, and team.
              (DPDP data-portability)
            </p>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={handleExport}
            disabled={exportLoading}
            aria-label="Download a JSON export of your organisation data"
            className="shrink-0"
          >
            {exportLoading ? (
              <>
                <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />
                Downloading…
              </>
            ) : (
              <>
                <Download className="mr-1.5 h-4 w-4" />
                Download export
              </>
            )}
          </Button>
        </div>

        <div className="border-t border-zinc-100 dark:border-zinc-800" />

        {/* Email digest */}
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div className="space-y-1">
            <p className="text-sm font-medium leading-none">
              Email me a renewal digest
            </p>
            <p className="text-xs text-zinc-500 dark:text-zinc-400 max-w-sm">
              Send yourself a summary of policies expiring in the next 30 days.
            </p>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={handleDigest}
            disabled={digestLoading}
            aria-label="Send a renewal digest email to yourself"
            className="shrink-0"
          >
            {digestLoading ? (
              <>
                <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />
                Sending…
              </>
            ) : (
              <>
                <Mail className="mr-1.5 h-4 w-4" />
                Send digest
              </>
            )}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

// ── Helpers ──────────────────────────────────────────────
function RoleBadge({ role }: { role: string }) {
  const v: Record<string, "default" | "secondary" | "warning" | "success"> = {
    admin: "default",
    manager: "warning",
    owner: "success",
    viewer: "secondary",
  };
  return (
    <Badge variant={v[role] ?? "secondary"} className="capitalize">
      {role}
    </Badge>
  );
}

function TeamSkeleton() {
  return (
    <div className="space-y-8 max-w-4xl mx-auto">
      <div className="space-y-1">
        <Skeleton className="h-8 w-24" />
        <Skeleton className="h-4 w-56" />
      </div>
      <Card>
        <CardHeader>
          <Skeleton className="h-4 w-24" />
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            {Array.from({ length: 3 }).map((_, i) => (
              <div key={i} className="flex items-center gap-4">
                <Skeleton className="h-8 w-48" />
                <Skeleton className="h-8 w-28" />
                <Skeleton className="h-5 w-9 rounded-full" />
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

function ErrorState({ message }: { message: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-24 text-center">
      <AlertTriangle className="mb-3 h-10 w-10 text-red-400" />
      <h3 className="font-semibold">Failed to load team</h3>
      <p className="mt-1 text-sm text-zinc-500">{message}</p>
    </div>
  );
}
