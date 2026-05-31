"use client";

import { useEffect, useState, useCallback } from "react";
import {
  getProviders,
  createProvider,
  type ProviderRead,
  type ProviderCreate,
} from "@/lib/api";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Card, CardContent } from "@/components/ui/card";
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
  Building2,
  Plus,
  Loader2,
  Mail,
  Phone,
  User,
  AlertTriangle,
} from "lucide-react";

interface Props {
  token: string;
}

export default function ProvidersClient({ token }: Props) {
  const [providers, setProviders] = useState<ProviderRead[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [dialogOpen, setDialogOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const [formName, setFormName] = useState("");
  const [formContactName, setFormContactName] = useState("");
  const [formContactEmail, setFormContactEmail] = useState("");
  const [formContactPhone, setFormContactPhone] = useState("");
  const [formNotes, setFormNotes] = useState("");

  const fetchProviders = useCallback(() => {
    if (!token) return;
    setLoading(true);
    getProviders(token)
      .then((res) => {
        setProviders(Array.isArray(res) ? res : []);
        setError(null);
      })
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false));
  }, [token]);

  useEffect(() => {
    fetchProviders();
  }, [fetchProviders]);

  function resetForm() {
    setFormName("");
    setFormContactName("");
    setFormContactEmail("");
    setFormContactPhone("");
    setFormNotes("");
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const trimmedName = formName.trim();
    if (!trimmedName) return;

    setSubmitting(true);
    try {
      const body: ProviderCreate = {
        name: trimmedName,
        ...(formContactName.trim() && { contact_name: formContactName.trim() }),
        ...(formContactEmail.trim() && {
          contact_email: formContactEmail.trim(),
        }),
        ...(formContactPhone.trim() && {
          contact_phone: formContactPhone.trim(),
        }),
        ...(formNotes.trim() && { notes: formNotes.trim() }),
      };
      await createProvider(token, body);
      toast.success("Provider added.");
      setDialogOpen(false);
      resetForm();
      fetchProviders();
    } catch {
      // apiFetch already showed a toast
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold tracking-tight flex items-center gap-2">
            <Building2 className="h-6 w-6 text-brand-600" />
            Providers
          </h2>
          <p className="text-sm text-zinc-500 dark:text-zinc-400 mt-0.5">
            Insurers and brokers your policies are placed with.
          </p>
        </div>

        <Dialog
          open={dialogOpen}
          onOpenChange={(v) => {
            setDialogOpen(v);
            if (!v) resetForm();
          }}
        >
          <DialogTrigger asChild>
            <Button size="sm" className="shrink-0">
              <Plus className="mr-1.5 h-4 w-4" />
              Add provider
            </Button>
          </DialogTrigger>
          <DialogContent className="max-w-md">
            <DialogHeader>
              <DialogTitle>Add Provider</DialogTitle>
            </DialogHeader>
            <form onSubmit={handleSubmit} className="space-y-4 py-2">
              <div className="space-y-1.5">
                <Label htmlFor="providerName">Name *</Label>
                <Input
                  id="providerName"
                  placeholder="e.g. ICICI Lombard, HDFC Ergo"
                  value={formName}
                  onChange={(e) => setFormName(e.target.value)}
                  disabled={submitting}
                  required
                  autoFocus
                />
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="providerContactName">
                  Contact name{" "}
                  <span className="text-zinc-400 font-normal">(optional)</span>
                </Label>
                <Input
                  id="providerContactName"
                  placeholder="Relationship manager name"
                  value={formContactName}
                  onChange={(e) => setFormContactName(e.target.value)}
                  disabled={submitting}
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1.5">
                  <Label htmlFor="providerContactEmail">
                    Email{" "}
                    <span className="text-zinc-400 font-normal">(optional)</span>
                  </Label>
                  <Input
                    id="providerContactEmail"
                    type="email"
                    placeholder="contact@insurer.com"
                    value={formContactEmail}
                    onChange={(e) => setFormContactEmail(e.target.value)}
                    disabled={submitting}
                  />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="providerContactPhone">
                    Phone{" "}
                    <span className="text-zinc-400 font-normal">(optional)</span>
                  </Label>
                  <Input
                    id="providerContactPhone"
                    type="tel"
                    placeholder="+91 98765 43210"
                    value={formContactPhone}
                    onChange={(e) => setFormContactPhone(e.target.value)}
                    disabled={submitting}
                  />
                </div>
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="providerNotes">
                  Notes{" "}
                  <span className="text-zinc-400 font-normal">(optional)</span>
                </Label>
                <textarea
                  id="providerNotes"
                  rows={3}
                  placeholder="Any notes about this insurer or broker…"
                  value={formNotes}
                  onChange={(e) => setFormNotes(e.target.value)}
                  disabled={submitting}
                  className={cn(
                    "w-full rounded-md border border-zinc-200 bg-transparent px-3 py-2 text-sm",
                    "placeholder:text-zinc-400 focus:outline-none focus:ring-2 focus:ring-brand-600",
                    "dark:border-zinc-800 dark:text-zinc-100 dark:placeholder:text-zinc-600",
                    "resize-none disabled:cursor-not-allowed disabled:opacity-50"
                  )}
                />
              </div>

              <DialogFooter>
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => setDialogOpen(false)}
                  disabled={submitting}
                >
                  Cancel
                </Button>
                <Button
                  type="submit"
                  disabled={submitting || !formName.trim()}
                  className="bg-brand-600 hover:bg-brand-600/90"
                >
                  {submitting ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      Adding…
                    </>
                  ) : (
                    "Add provider"
                  )}
                </Button>
              </DialogFooter>
            </form>
          </DialogContent>
        </Dialog>
      </div>

      {/* Content area */}
      {loading ? (
        <SkeletonGrid />
      ) : error ? (
        <ErrorState message={error} onRetry={fetchProviders} />
      ) : providers.length === 0 ? (
        <EmptyState onAdd={() => setDialogOpen(true)} />
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {providers.map((provider) => (
            <ProviderCard key={provider.id} provider={provider} />
          ))}
        </div>
      )}
    </div>
  );
}

function ProviderCard({ provider }: { provider: ProviderRead }) {
  const hasAnyContact =
    provider.contact_name || provider.contact_email || provider.contact_phone;

  return (
    <Card className="rounded-xl border border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900 shadow-none">
      <CardContent className="p-4 space-y-3">
        <div className="flex items-start gap-2">
          <Building2 className="mt-0.5 h-4 w-4 shrink-0 text-brand-600" />
          <span className="font-semibold text-sm leading-snug">
            {provider.name}
          </span>
        </div>

        {hasAnyContact ? (
          <div className="space-y-1.5 pt-0.5">
            {provider.contact_name && (
              <div className="flex items-center gap-2 text-sm text-zinc-600 dark:text-zinc-400">
                <User className="h-3.5 w-3.5 shrink-0 text-zinc-400 dark:text-zinc-500" />
                <span className="truncate">{provider.contact_name}</span>
              </div>
            )}
            {provider.contact_email && (
              <div className="flex items-center gap-2 text-sm text-zinc-600 dark:text-zinc-400">
                <Mail className="h-3.5 w-3.5 shrink-0 text-zinc-400 dark:text-zinc-500" />
                <a
                  href={`mailto:${provider.contact_email}`}
                  className="truncate hover:text-brand-600 dark:hover:text-brand-400 transition-colors"
                  aria-label={`Email ${provider.contact_name ?? provider.name} at ${provider.contact_email}`}
                >
                  {provider.contact_email}
                </a>
              </div>
            )}
            {provider.contact_phone && (
              <div className="flex items-center gap-2 text-sm text-zinc-600 dark:text-zinc-400">
                <Phone className="h-3.5 w-3.5 shrink-0 text-zinc-400 dark:text-zinc-500" />
                <a
                  href={`tel:${provider.contact_phone}`}
                  className="truncate hover:text-brand-600 dark:hover:text-brand-400 transition-colors"
                  aria-label={`Call ${provider.contact_name ?? provider.name} at ${provider.contact_phone}`}
                >
                  {provider.contact_phone}
                </a>
              </div>
            )}
          </div>
        ) : (
          <p className="text-xs text-zinc-400 dark:text-zinc-500 pt-0.5">
            No contact details
          </p>
        )}
      </CardContent>
    </Card>
  );
}

function SkeletonGrid() {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
      {Array.from({ length: 6 }).map((_, i) => (
        <div
          key={i}
          className="rounded-xl border border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900 p-4 space-y-3"
        >
          <Skeleton className="h-4 w-3/4" />
          <div className="space-y-2 pt-1">
            <Skeleton className="h-3.5 w-full" />
            <Skeleton className="h-3.5 w-5/6" />
            <Skeleton className="h-3.5 w-2/3" />
          </div>
        </div>
      ))}
    </div>
  );
}

function EmptyState({ onAdd }: { onAdd: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center py-20 text-center rounded-xl border border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900">
      <Building2 className="mb-3 h-10 w-10 text-zinc-300 dark:text-zinc-600" />
      <h3 className="font-semibold">No providers yet</h3>
      <p className="mt-1 text-sm text-zinc-400">
        Add the insurers and brokers your policies are placed with.
      </p>
      <Button size="sm" className="mt-4" onClick={onAdd}>
        <Plus className="mr-1.5 h-4 w-4" />
        Add provider
      </Button>
    </div>
  );
}

function ErrorState({
  message,
  onRetry,
}: {
  message: string;
  onRetry: () => void;
}) {
  return (
    <div className="flex flex-col items-center justify-center py-20 text-center rounded-xl border border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900">
      <AlertTriangle className="mb-3 h-10 w-10 text-red-400" />
      <h3 className="font-semibold">Failed to load providers</h3>
      <p className="mt-1 text-sm text-zinc-500">{message}</p>
      <Button size="sm" variant="outline" className="mt-4" onClick={onRetry}>
        Retry
      </Button>
    </div>
  );
}
