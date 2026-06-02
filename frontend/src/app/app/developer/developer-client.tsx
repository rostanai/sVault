"use client";

import { useEffect, useState, useCallback } from "react";
import {
  getApiKeys,
  createApiKey,
  revokeApiKey,
  getWebhooks,
  createWebhook,
  deleteWebhook,
  testWebhook,
  type ApiKeyRead,
  type ApiKeyCreated,
  type WebhookRead,
  type WebhookCreated,
} from "@/lib/api";
import { formatDate, cn } from "@/lib/utils";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import { Skeleton } from "@/components/ui/skeleton";
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
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
  DialogFooter,
} from "@/components/ui/dialog";
import { toast } from "sonner";
import {
  Code2,
  KeyRound,
  Webhook,
  Plus,
  Trash2,
  Copy,
  Check,
  Loader2,
  AlertTriangle,
  Send,
} from "lucide-react";

// ── Constants ───────────────────────────────────────────────────────────

const WEBHOOK_EVENTS = [
  "policy.created",
  "renewal.due",
  "approval.pending",
  "payment.failed",
  "webhook.test",
] as const;

type WebhookEvent = (typeof WEBHOOK_EVENTS)[number];

// ── Props ─────────────────────────────────────────────────────────────────

interface Props {
  token: string;
}

// ── Root component ───────────────────────────────────────────────────────

export default function DeveloperClient({ token }: Props) {
  return (
    <div className="space-y-6 max-w-6xl mx-auto">
      {/* Page header */}
      <div className="flex items-start gap-3">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-brand-600 text-white">
          <Code2 className="h-5 w-5" />
        </div>
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Developer</h1>
          <p className="text-sm text-zinc-500 dark:text-zinc-400 mt-0.5">
            API keys and webhooks for third-party integration.
          </p>
        </div>
      </div>

      {/* Tabs */}
      <Tabs defaultValue="api-keys" className="space-y-4">
        <TabsList className="w-full sm:w-auto">
          <TabsTrigger value="api-keys" className="gap-1.5">
            <KeyRound className="h-3.5 w-3.5" />
            API Keys
          </TabsTrigger>
          <TabsTrigger value="webhooks" className="gap-1.5">
            <Webhook className="h-3.5 w-3.5" />
            Webhooks
          </TabsTrigger>
        </TabsList>

        <TabsContent value="api-keys">
          <ApiKeysTab token={token} />
        </TabsContent>
        <TabsContent value="webhooks">
          <WebhooksTab token={token} />
        </TabsContent>
      </Tabs>
    </div>
  );
}

// ── API Keys Tab ─────────────────────────────────────────────────────────────

function ApiKeysTab({ token }: { token: string }) {
  const [keys, setKeys] = useState<ApiKeyRead[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchKeys = useCallback(() => {
    setLoading(true);
    setError(null);
    getApiKeys(token)
      .then(setKeys)
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false));
  }, [token]);

  useEffect(() => {
    if (token) fetchKeys();
  }, [fetchKeys, token]);

  if (loading) return <TableSkeleton rows={3} cols={6} />;
  if (error) return <TabError message={error} onRetry={fetchKeys} />;

  return (
    <div className="space-y-4">
      {/* Info banner */}
      <div className="rounded-lg border border-zinc-200 bg-zinc-50 px-4 py-3 text-sm text-zinc-600 dark:border-zinc-700 dark:bg-zinc-800/60 dark:text-zinc-400">
        <strong className="font-semibold text-zinc-800 dark:text-zinc-200">
          Security note:
        </strong>{" "}
        API keys are shown in full only at creation time. Store them securely — they cannot be retrieved later.
        Authenticate requests with{" "}
        <code className="rounded bg-zinc-200 px-1 py-0.5 font-mono text-xs dark:bg-zinc-700">
          Authorization: Bearer &lt;key&gt;
        </code>
        .
      </div>

      {/* Header row */}
      <div className="flex items-center justify-between">
        <p className="text-sm text-zinc-500 dark:text-zinc-400">
          {keys.length} key{keys.length !== 1 ? "s" : ""}
          {keys.length > 0
            ? ` (${keys.filter((k) => !k.revoked_at).length} active)`
            : ""}
        </p>
        <CreateKeyDialog token={token} onCreated={fetchKeys} />
      </div>

      {keys.length === 0 ? (
        <EmptyState icon={KeyRound} message="No API keys yet. Create one to get started." />
      ) : (
        <div className="rounded-xl border border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900 overflow-hidden">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>Key Prefix</TableHead>
                <TableHead>Scopes</TableHead>
                <TableHead>Last Used</TableHead>
                <TableHead>Created</TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="text-right">Action</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {keys.map((key) => (
                <ApiKeyRow
                  key={key.id}
                  apiKey={key}
                  token={token}
                  onRevoked={fetchKeys}
                />
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  );
}

function ApiKeyRow({
  apiKey,
  token,
  onRevoked,
}: {
  apiKey: ApiKeyRead;
  token: string;
  onRevoked: () => void;
}) {
  const isRevoked = !!apiKey.revoked_at;
  const [revoking, setRevoking] = useState(false);
  const [confirmOpen, setConfirmOpen] = useState(false);

  async function handleRevoke() {
    setRevoking(true);
    setConfirmOpen(false);
    try {
      await revokeApiKey(token, apiKey.id);
      toast.success(`Key "${apiKey.name}" revoked.`);
      onRevoked();
    } catch {
      // apiFetch already toasted
    } finally {
      setRevoking(false);
    }
  }

  return (
    <TableRow className={cn(isRevoked && "opacity-60")}>
      <TableCell className="font-medium">{apiKey.name}</TableCell>
      <TableCell>
        <code className="rounded bg-zinc-100 px-1.5 py-0.5 font-mono text-xs text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300 select-all">
          {apiKey.prefix}&hellip;
        </code>
      </TableCell>
      <TableCell>
        {apiKey.scopes.length === 0 ? (
          <span className="text-xs text-zinc-400">All scopes</span>
        ) : (
          <div className="flex flex-wrap gap-1">
            {apiKey.scopes.map((scope) => (
              <Badge key={scope} variant="secondary" className="font-mono text-xs">
                {scope}
              </Badge>
            ))}
          </div>
        )}
      </TableCell>
      <TableCell className="text-sm text-zinc-500 whitespace-nowrap">
        {apiKey.last_used_at ? formatDate(apiKey.last_used_at) : "Never"}
      </TableCell>
      <TableCell className="text-sm text-zinc-500 whitespace-nowrap">
        {formatDate(apiKey.created_at)}
      </TableCell>
      <TableCell>
        <Badge variant={isRevoked ? "destructive" : "success"}>
          {isRevoked ? "Revoked" : "Active"}
        </Badge>
      </TableCell>
      <TableCell className="text-right">
        {isRevoked ? (
          <span className="text-xs text-zinc-400">—</span>
        ) : revoking ? (
          <Loader2 className="ml-auto h-4 w-4 animate-spin text-zinc-400" />
        ) : (
          <>
            <Dialog open={confirmOpen} onOpenChange={setConfirmOpen}>
              <DialogTrigger asChild>
                <Button
                  size="sm"
                  variant="outline"
                  className="h-7 px-2.5 text-xs text-red-600 border-red-200 hover:bg-red-50 dark:border-red-800 dark:text-red-400 dark:hover:bg-red-900/20"
                  aria-label={`Revoke API key ${apiKey.name}`}
                >
                  Revoke
                </Button>
              </DialogTrigger>
              <DialogContent className="max-w-md">
                <DialogHeader>
                  <DialogTitle>Revoke API Key?</DialogTitle>
                </DialogHeader>
                <p className="text-sm text-zinc-600 dark:text-zinc-400">
                  This will permanently revoke{" "}
                  <strong className="font-semibold text-zinc-800 dark:text-zinc-200">
                    {apiKey.name}
                  </strong>
                  . Any integrations using this key will stop working
                  immediately. This cannot be undone.
                </p>
                <DialogFooter>
                  <Button
                    variant="outline"
                    onClick={() => setConfirmOpen(false)}
                  >
                    Cancel
                  </Button>
                  <Button
                    onClick={handleRevoke}
                    className="bg-red-600 text-white hover:bg-red-700 focus-visible:ring-red-600"
                  >
                    Revoke key
                  </Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
          </>
        )}
      </TableCell>
    </TableRow>
  );
}

// ── Create Key Dialog ─────────────────────────────────────────────────────────

function CreateKeyDialog({
  token,
  onCreated,
}: {
  token: string;
  onCreated: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [creating, setCreating] = useState(false);

  // Form state
  const [name, setName] = useState("");
  const [scopesRaw, setScopesRaw] = useState("");
  const [expiresInDays, setExpiresInDays] = useState("");

  // "Shown once" state — set after successful creation, cleared on close
  const [createdKey, setCreatedKey] = useState<ApiKeyCreated | null>(null);
  const [copied, setCopied] = useState(false);

  function resetForm() {
    setName("");
    setScopesRaw("");
    setExpiresInDays("");
    setCreatedKey(null);
    setCopied(false);
  }

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;

    const scopes = scopesRaw
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);

    const expiresNum = expiresInDays.trim() ? parseInt(expiresInDays.trim(), 10) : undefined;

    setCreating(true);
    try {
      const created = await createApiKey(token, {
        name: name.trim(),
        scopes: scopes.length > 0 ? scopes : undefined,
        expires_in_days: expiresNum,
      });
      setCreatedKey(created);
      toast.success("API key created.");
      onCreated();
    } catch {
      // apiFetch already toasted
    } finally {
      setCreating(false);
    }
  }

  async function handleCopy() {
    if (!createdKey) return;
    try {
      await navigator.clipboard.writeText(createdKey.plaintext_key);
      setCopied(true);
      toast.success("Key copied to clipboard.");
      setTimeout(() => setCopied(false), 2500);
    } catch {
      toast.error("Could not copy — please select and copy manually.");
    }
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(v) => {
        setOpen(v);
        if (!v) resetForm();
      }}
    >
      <DialogTrigger asChild>
        <Button size="sm">
          <Plus className="mr-1.5 h-4 w-4" />
          Create key
        </Button>
      </DialogTrigger>

      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Create API Key</DialogTitle>
        </DialogHeader>

        {/* "Shown once" display — rendered INSTEAD of form after creation */}
        {createdKey ? (
          <div className="space-y-4 py-2">
            {/* Warning banner */}
            <div className="flex items-start gap-2.5 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 dark:border-amber-700 dark:bg-amber-900/20">
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-600 dark:text-amber-400" />
              <p className="text-sm text-amber-800 dark:text-amber-300">
                <strong className="font-semibold">Copy this key now.</strong> It
                will not be shown again. Store it in a secure secrets manager.
              </p>
            </div>

            {/* Key display */}
            <div className="space-y-1.5">
              <Label>Your new API key</Label>
              <div className="flex items-center gap-2">
                <code
                  className={cn(
                    "flex-1 rounded-lg border border-zinc-200 bg-zinc-50 px-3 py-2.5",
                    "font-mono text-sm text-zinc-800 break-all select-all",
                    "dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-100"
                  )}
                  aria-label="Plaintext API key — copy before closing"
                >
                  {createdKey.plaintext_key}
                </code>
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  onClick={handleCopy}
                  aria-label={copied ? "Copied to clipboard" : "Copy API key to clipboard"}
                  className="shrink-0"
                >
                  {copied ? (
                    <Check className="h-4 w-4 text-emerald-600" />
                  ) : (
                    <Copy className="h-4 w-4" />
                  )}
                </Button>
              </div>
            </div>

            {/* Metadata */}
            <dl className="grid grid-cols-2 gap-x-4 gap-y-1.5 text-sm">
              <dt className="text-zinc-500">Name</dt>
              <dd className="font-medium">{createdKey.name}</dd>
              <dt className="text-zinc-500">Prefix</dt>
              <dd className="font-mono text-xs">{createdKey.prefix}&hellip;</dd>
              <dt className="text-zinc-500">Scopes</dt>
              <dd>
                {createdKey.scopes.length === 0 ? (
                  <span className="text-zinc-400">All scopes</span>
                ) : (
                  createdKey.scopes.join(", ")
                )}
              </dd>
              <dt className="text-zinc-500">Expires</dt>
              <dd>{createdKey.expires_at ? formatDate(createdKey.expires_at) : "Never"}</dd>
            </dl>

            <DialogFooter>
              <Button
                onClick={() => {
                  setOpen(false);
                  resetForm();
                }}
              >
                Done
              </Button>
            </DialogFooter>
          </div>
        ) : (
          /* Creation form */
          <form onSubmit={handleCreate} className="space-y-4 py-2">
            <div className="space-y-1.5">
              <Label htmlFor="key-name">
                Name <span aria-hidden>*</span>
              </Label>
              <Input
                id="key-name"
                placeholder="e.g. CI Pipeline, ERP Integration"
                value={name}
                onChange={(e) => setName(e.target.value)}
                disabled={creating}
                required
                autoFocus
              />
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="key-scopes">
                Scopes{" "}
                <span className="text-zinc-400 font-normal">(comma-separated, leave blank for all)</span>
              </Label>
              <Input
                id="key-scopes"
                placeholder="policies:read, documents:read"
                value={scopesRaw}
                onChange={(e) => setScopesRaw(e.target.value)}
                disabled={creating}
                className="font-mono text-sm"
              />
              <p className="text-xs text-zinc-400">
                Example scopes: <code className="font-mono">policies:read</code>,{" "}
                <code className="font-mono">policies:write</code>,{" "}
                <code className="font-mono">documents:read</code>
              </p>
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="key-expires">
                Expires in days{" "}
                <span className="text-zinc-400 font-normal">(leave blank for no expiry)</span>
              </Label>
              <Input
                id="key-expires"
                type="number"
                min="1"
                max="3650"
                placeholder="e.g. 365"
                value={expiresInDays}
                onChange={(e) => setExpiresInDays(e.target.value)}
                disabled={creating}
                className="max-w-[160px]"
              />
            </div>

            <DialogFooter>
              <Button
                type="button"
                variant="outline"
                onClick={() => setOpen(false)}
                disabled={creating}
              >
                Cancel
              </Button>
              <Button type="submit" disabled={creating || !name.trim()}>
                {creating ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Creating…
                  </>
                ) : (
                  "Create key"
                )}
              </Button>
            </DialogFooter>
          </form>
        )}
      </DialogContent>
    </Dialog>
  );
}

// ── Webhooks Tab ──────────────────────────────────────────────────────────────

function WebhooksTab({ token }: { token: string }) {
  const [hooks, setHooks] = useState<WebhookRead[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchHooks = useCallback(() => {
    setLoading(true);
    setError(null);
    getWebhooks(token)
      .then(setHooks)
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false));
  }, [token]);

  useEffect(() => {
    if (token) fetchHooks();
  }, [fetchHooks, token]);

  if (loading) return <TableSkeleton rows={3} cols={5} />;
  if (error) return <TabError message={error} onRetry={fetchHooks} />;

  return (
    <div className="space-y-4">
      {/* Info banner */}
      <div className="rounded-lg border border-zinc-200 bg-zinc-50 px-4 py-3 text-sm text-zinc-600 dark:border-zinc-700 dark:bg-zinc-800/60 dark:text-zinc-400">
        <strong className="font-semibold text-zinc-800 dark:text-zinc-200">
          Webhook security:
        </strong>{" "}
        sVault signs every webhook payload with an HMAC-SHA256 signature in the{" "}
        <code className="rounded bg-zinc-200 px-1 py-0.5 font-mono text-xs dark:bg-zinc-700">
          X-sVault-Signature
        </code>{" "}
        header. Verify it against your webhook secret to prevent spoofing.
      </div>

      {/* Header row */}
      <div className="flex items-center justify-between">
        <p className="text-sm text-zinc-500 dark:text-zinc-400">
          {hooks.length} webhook{hooks.length !== 1 ? "s" : ""}
          {hooks.length > 0
            ? ` (${hooks.filter((h) => h.is_active).length} active)`
            : ""}
        </p>
        <AddWebhookDialog token={token} onCreated={fetchHooks} />
      </div>

      {hooks.length === 0 ? (
        <EmptyState icon={Webhook} message="No webhooks configured yet. Add one to receive real-time events." />
      ) : (
        <div className="rounded-xl border border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900 overflow-hidden">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>URL</TableHead>
                <TableHead>Events</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Created</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {hooks.map((hook) => (
                <WebhookRow
                  key={hook.id}
                  hook={hook}
                  token={token}
                  onDeleted={fetchHooks}
                />
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  );
}

function WebhookRow({
  hook,
  token,
  onDeleted,
}: {
  hook: WebhookRead;
  token: string;
  onDeleted: () => void;
}) {
  const [testing, setTesting] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [confirmDeleteOpen, setConfirmDeleteOpen] = useState(false);

  async function handleTest() {
    setTesting(true);
    try {
      const result = await testWebhook(token, hook.id);
      if (result.delivered) {
        toast.success(
          `Delivered (${result.status_code ?? "—"})`,
          { description: hook.url }
        );
      } else {
        toast.error(
          `Failed${result.status_code != null ? ` (${result.status_code})` : ""}`,
          { description: hook.url }
        );
      }
    } catch {
      // apiFetch already toasted
    } finally {
      setTesting(false);
    }
  }

  async function handleDelete() {
    setDeleting(true);
    setConfirmDeleteOpen(false);
    try {
      await deleteWebhook(token, hook.id);
      toast.success("Webhook deleted.");
      onDeleted();
    } catch {
      // apiFetch already toasted
    } finally {
      setDeleting(false);
    }
  }

  const inFlight = testing || deleting;

  return (
    <TableRow>
      <TableCell className="max-w-[240px]">
        <code
          className="block truncate font-mono text-xs text-zinc-700 dark:text-zinc-300"
          title={hook.url}
        >
          {hook.url}
        </code>
      </TableCell>
      <TableCell>
        <div className="flex flex-wrap gap-1">
          {hook.events.map((ev) => (
            <Badge key={ev} variant="secondary" className="font-mono text-xs">
              {ev}
            </Badge>
          ))}
        </div>
      </TableCell>
      <TableCell>
        <Badge variant={hook.is_active ? "success" : "secondary"}>
          {hook.is_active ? "Active" : "Inactive"}
        </Badge>
      </TableCell>
      <TableCell className="text-sm text-zinc-500 whitespace-nowrap">
        {formatDate(hook.created_at)}
      </TableCell>
      <TableCell className="text-right">
        <div className="flex items-center justify-end gap-2">
          {/* Test button */}
          <Button
            size="sm"
            variant="outline"
            className="h-7 px-2.5 text-xs gap-1"
            onClick={handleTest}
            disabled={inFlight}
            aria-label={`Send test event to ${hook.url}`}
          >
            {testing ? (
              <Loader2 className="h-3 w-3 animate-spin" />
            ) : (
              <Send className="h-3 w-3" />
            )}
            Test
          </Button>

          {/* Delete with confirm dialog */}
          {deleting ? (
            <Loader2 className="h-4 w-4 animate-spin text-zinc-400" />
          ) : (
            <Dialog open={confirmDeleteOpen} onOpenChange={setConfirmDeleteOpen}>
              <DialogTrigger asChild>
                <Button
                  size="sm"
                  variant="outline"
                  className="h-7 px-2.5 text-xs text-red-600 border-red-200 hover:bg-red-50 dark:border-red-800 dark:text-red-400 dark:hover:bg-red-900/20"
                  disabled={inFlight}
                  aria-label={`Delete webhook for ${hook.url}`}
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </Button>
              </DialogTrigger>
              <DialogContent className="max-w-md">
                <DialogHeader>
                  <DialogTitle>Delete Webhook?</DialogTitle>
                </DialogHeader>
                <p className="text-sm text-zinc-600 dark:text-zinc-400">
                  This will permanently delete the webhook endpoint{" "}
                  <strong className="font-medium break-all text-zinc-800 dark:text-zinc-200">
                    {hook.url}
                  </strong>
                  . sVault will stop sending events to it immediately.
                </p>
                <DialogFooter>
                  <Button
                    variant="outline"
                    onClick={() => setConfirmDeleteOpen(false)}
                  >
                    Cancel
                  </Button>
                  <Button
                    onClick={handleDelete}
                    className="bg-red-600 text-white hover:bg-red-700 focus-visible:ring-red-600"
                  >
                    Delete webhook
                  </Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
          )}
        </div>
      </TableCell>
    </TableRow>
  );
}

// ── Add Webhook Dialog ───────────────────────────────────────────────────────

function AddWebhookDialog({
  token,
  onCreated,
}: {
  token: string;
  onCreated: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [creating, setCreating] = useState(false);

  // Form state
  const [url, setUrl] = useState("");
  const [selectedEvents, setSelectedEvents] = useState<Set<WebhookEvent>>(new Set());

  // "Shown once" state
  const [createdHook, setCreatedHook] = useState<WebhookCreated | null>(null);
  const [copied, setCopied] = useState(false);

  function resetForm() {
    setUrl("");
    setSelectedEvents(new Set());
    setCreatedHook(null);
    setCopied(false);
  }

  function toggleEvent(event: WebhookEvent) {
    setSelectedEvents((prev) => {
      const next = new Set(prev);
      if (next.has(event)) {
        next.delete(event);
      } else {
        next.add(event);
      }
      return next;
    });
  }

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!url.trim() || selectedEvents.size === 0) return;

    setCreating(true);
    try {
      const created = await createWebhook(token, {
        url: url.trim(),
        events: Array.from(selectedEvents),
      });
      setCreatedHook(created);
      toast.success("Webhook registered.");
      onCreated();
    } catch {
      // apiFetch already toasted
    } finally {
      setCreating(false);
    }
  }

  async function handleCopy() {
    if (!createdHook) return;
    try {
      await navigator.clipboard.writeText(createdHook.secret);
      setCopied(true);
      toast.success("Webhook secret copied to clipboard.");
      setTimeout(() => setCopied(false), 2500);
    } catch {
      toast.error("Could not copy — please select and copy manually.");
    }
  }

  const canSubmit = url.trim().length > 0 && selectedEvents.size > 0;

  return (
    <Dialog
      open={open}
      onOpenChange={(v) => {
        setOpen(v);
        if (!v) resetForm();
      }}
    >
      <DialogTrigger asChild>
        <Button size="sm">
          <Plus className="mr-1.5 h-4 w-4" />
          Add webhook
        </Button>
      </DialogTrigger>

      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Add Webhook</DialogTitle>
        </DialogHeader>

        {/* "Shown once" secret display */}
        {createdHook ? (
          <div className="space-y-4 py-2">
            {/* Warning banner */}
            <div className="flex items-start gap-2.5 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 dark:border-amber-700 dark:bg-amber-900/20">
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-600 dark:text-amber-400" />
              <p className="text-sm text-amber-800 dark:text-amber-300">
                <strong className="font-semibold">Save this webhook secret now.</strong>{" "}
                Use it to verify the{" "}
                <code className="rounded bg-amber-100 px-1 py-0.5 font-mono text-xs dark:bg-amber-900/40">
                  X-sVault-Signature
                </code>{" "}
                HMAC-SHA256 header on every incoming request. It will not be shown again.
              </p>
            </div>

            {/* Secret display */}
            <div className="space-y-1.5">
              <Label>Webhook signing secret</Label>
              <div className="flex items-center gap-2">
                <code
                  className={cn(
                    "flex-1 rounded-lg border border-zinc-200 bg-zinc-50 px-3 py-2.5",
                    "font-mono text-sm text-zinc-800 break-all select-all",
                    "dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-100"
                  )}
                  aria-label="Webhook signing secret — copy before closing"
                >
                  {createdHook.secret}
                </code>
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  onClick={handleCopy}
                  aria-label={
                    copied ? "Copied to clipboard" : "Copy webhook secret to clipboard"
                  }
                  className="shrink-0"
                >
                  {copied ? (
                    <Check className="h-4 w-4 text-emerald-600" />
                  ) : (
                    <Copy className="h-4 w-4" />
                  )}
                </Button>
              </div>
            </div>

            {/* Metadata */}
            <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5 text-sm">
              <dt className="text-zinc-500">URL</dt>
              <dd className="font-mono text-xs break-all">{createdHook.url}</dd>
              <dt className="text-zinc-500">Events</dt>
              <dd className="flex flex-wrap gap-1">
                {createdHook.events.map((ev) => (
                  <Badge key={ev} variant="secondary" className="font-mono text-xs">
                    {ev}
                  </Badge>
                ))}
              </dd>
            </dl>

            <DialogFooter>
              <Button
                onClick={() => {
                  setOpen(false);
                  resetForm();
                }}
              >
                Done
              </Button>
            </DialogFooter>
          </div>
        ) : (
          /* Creation form */
          <form onSubmit={handleCreate} className="space-y-4 py-2">
            <div className="space-y-1.5">
              <Label htmlFor="wh-url">
                Endpoint URL <span aria-hidden>*</span>
              </Label>
              <Input
                id="wh-url"
                type="url"
                placeholder="https://your-server.example.com/webhooks/svault"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                disabled={creating}
                required
                autoFocus
                className="font-mono text-sm"
              />
            </div>

            <fieldset className="space-y-2">
              <legend className="text-sm font-medium leading-none">
                Events to subscribe to <span aria-hidden>*</span>
              </legend>
              <p className="text-xs text-zinc-400">
                sVault will POST a signed JSON payload to your endpoint for each selected event.
              </p>
              <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                {WEBHOOK_EVENTS.map((ev) => (
                  <div key={ev} className="flex items-center gap-2.5">
                    <Checkbox
                      id={`wh-event-${ev}`}
                      checked={selectedEvents.has(ev)}
                      onCheckedChange={() => toggleEvent(ev)}
                      disabled={creating}
                      aria-label={`Subscribe to ${ev} events`}
                    />
                    <label
                      htmlFor={`wh-event-${ev}`}
                      className={cn(
                        "cursor-pointer select-none font-mono text-xs text-zinc-700 dark:text-zinc-300",
                        creating && "cursor-not-allowed opacity-60"
                      )}
                    >
                      {ev}
                    </label>
                  </div>
                ))}
              </div>
              {selectedEvents.size === 0 && (
                <p className="text-xs text-amber-600 dark:text-amber-400" role="alert">
                  Select at least one event.
                </p>
              )}
            </fieldset>

            <DialogFooter>
              <Button
                type="button"
                variant="outline"
                onClick={() => setOpen(false)}
                disabled={creating}
              >
                Cancel
              </Button>
              <Button type="submit" disabled={creating || !canSubmit}>
                {creating ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Adding…
                  </>
                ) : (
                  "Add webhook"
                )}
              </Button>
            </DialogFooter>
          </form>
        )}
      </DialogContent>
    </Dialog>
  );
}

// ── Shared helpers ──────────────────────────────────────────────────────────────

function TableSkeleton({ rows, cols }: { rows: number; cols: number }) {
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <Skeleton className="h-4 w-24" />
        <Skeleton className="h-9 w-28" />
      </div>
      <div className="rounded-xl border border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900">
        <div className="p-4 space-y-3">
          <div
            className="grid gap-4"
            style={{ gridTemplateColumns: `repeat(${cols}, minmax(0, 1fr))` }}
          >
            {Array.from({ length: cols }).map((_, i) => (
              <Skeleton key={i} className="h-4 w-full" />
            ))}
          </div>
          {Array.from({ length: rows }).map((_, i) => (
            <Skeleton key={i} className="h-10 w-full" />
          ))}
        </div>
      </div>
    </div>
  );
}

function EmptyState({
  icon: Icon,
  message,
}: {
  icon: React.ElementType;
  message: string;
}) {
  return (
    <div className="flex flex-col items-center justify-center py-20 text-center rounded-xl border border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900">
      <Icon className="mb-3 h-10 w-10 text-zinc-300" />
      <p className="text-sm font-medium text-zinc-500">{message}</p>
    </div>
  );
}

function TabError({
  message,
  onRetry,
}: {
  message: string;
  onRetry: () => void;
}) {
  return (
    <div className="flex flex-col items-center justify-center py-20 text-center rounded-xl border border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900">
      <AlertTriangle className="mb-3 h-10 w-10 text-red-400" />
      <h3 className="font-semibold">Failed to load</h3>
      <p className="mt-1 text-sm text-zinc-500">{message}</p>
      <Button size="sm" variant="outline" className="mt-4" onClick={onRetry}>
        Retry
      </Button>
    </div>
  );
}
