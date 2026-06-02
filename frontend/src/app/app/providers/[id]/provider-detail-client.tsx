"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import {
  getProvider,
  updateProvider,
  getProviderContacts,
  addProviderContact,
  deleteProviderContact,
  type ProviderRead,
  type ProviderUpdate,
  type ProviderContact,
  type ProviderContactCreate,
} from "@/lib/api";
import { formatDate, cn } from "@/lib/utils";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { toast } from "sonner";
import {
  ArrowLeft,
  AlertTriangle,
  Building2,
  Mail,
  Phone,
  User,
  Plus,
  Trash2,
  Phone as PhoneCall,
  MessageSquare,
  Calendar,
  StickyNote,
  Loader2,
  Pencil,
} from "lucide-react";

// ── Types ─────────────────────────────────────────────────────────
interface Props {
  id: string;
  token: string;
}

type ContactKind = "call" | "email" | "meeting" | "note";

const KIND_OPTIONS: { value: ContactKind; label: string }[] = [
  { value: "call", label: "Call" },
  { value: "email", label: "Email" },
  { value: "meeting", label: "Meeting" },
  { value: "note", label: "Note" },
];

function kindIcon(kind: string): React.ReactNode {
  switch (kind) {
    case "call":
      return <PhoneCall className="h-4 w-4 text-brand-600" aria-hidden="true" />;
    case "email":
      return <Mail className="h-4 w-4 text-brand-600" aria-hidden="true" />;
    case "meeting":
      return <Calendar className="h-4 w-4 text-brand-600" aria-hidden="true" />;
    case "note":
    default:
      return <StickyNote className="h-4 w-4 text-brand-600" aria-hidden="true" />;
  }
}

function todayISO(): string {
  return new Date().toISOString().slice(0, 10);
}

// ── Main component ───────────────────────────────────────────────
export default function ProviderDetailClient({ id, token }: Props) {
  const [provider, setProvider] = useState<ProviderRead | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [contacts, setContacts] = useState<ProviderContact[]>([]);
  const [contactsLoading, setContactsLoading] = useState(true);
  const [contactsError, setContactsError] = useState<string | null>(null);

  // Edit provider dialog
  const [editOpen, setEditOpen] = useState(false);
  const [editForm, setEditForm] = useState<ProviderUpdate>({});
  const [editSaving, setEditSaving] = useState(false);

  // Log contact dialog
  const [logOpen, setLogOpen] = useState(false);
  const [logKind, setLogKind] = useState<ContactKind>("call");
  const [logSubject, setLogSubject] = useState("");
  const [logNote, setLogNote] = useState("");
  const [logDate, setLogDate] = useState(todayISO());
  const [logSubmitting, setLogSubmitting] = useState(false);

  // Delete contact state
  const [deletingId, setDeletingId] = useState<string | null>(null);

  // ── Fetchers ───────────────────────────────────────────────────
  const fetchProvider = useCallback(() => {
    if (!token) return;
    setLoading(true);
    getProvider(token, id)
      .then((data) => {
        setProvider(data);
        setError(null);
      })
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false));
  }, [id, token]);

  const fetchContacts = useCallback(() => {
    if (!token) return;
    setContactsLoading(true);
    getProviderContacts(token, id)
      .then((data) => {
        // Newest first
        const sorted = [...data].sort(
          (a, b) =>
            new Date(b.contacted_at).getTime() -
            new Date(a.contacted_at).getTime()
        );
        setContacts(sorted);
        setContactsError(null);
      })
      .catch((err: Error) => setContactsError(err.message))
      .finally(() => setContactsLoading(false));
  }, [id, token]);

  useEffect(() => {
    fetchProvider();
    fetchContacts();
  }, [fetchProvider, fetchContacts]);

  // ── Edit provider ─────────────────────────────────────────────
  function openEdit() {
    if (!provider) return;
    setEditForm({
      name: provider.name,
      contact_name: provider.contact_name ?? "",
      contact_email: provider.contact_email ?? "",
      contact_phone: provider.contact_phone ?? "",
      notes: "",
    });
    setEditOpen(true);
  }

  async function handleEditSave(e: React.FormEvent) {
    e.preventDefault();
    if (!editForm.name?.trim()) return;
    setEditSaving(true);
    try {
      const body: ProviderUpdate = {
        name: editForm.name?.trim(),
        contact_name: editForm.contact_name?.trim() || null,
        contact_email: editForm.contact_email?.trim() || null,
        contact_phone: editForm.contact_phone?.trim() || null,
        ...(editForm.notes?.trim() ? { notes: editForm.notes.trim() } : {}),
      };
      const updated = await updateProvider(token, id, body);
      setProvider(updated);
      setEditOpen(false);
      toast.success("Provider updated.");
    } catch {
      // apiFetch already showed a toast
    } finally {
      setEditSaving(false);
    }
  }

  // ── Log contact ────────────────────────────────────────────────
  function resetLogForm() {
    setLogKind("call");
    setLogSubject("");
    setLogNote("");
    setLogDate(todayISO());
  }

  async function handleLogSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLogSubmitting(true);
    try {
      const body: ProviderContactCreate = {
        kind: logKind,
        ...(logSubject.trim() ? { subject: logSubject.trim() } : {}),
        ...(logNote.trim() ? { note: logNote.trim() } : {}),
        ...(logDate ? { contacted_at: logDate } : {}),
      };
      await addProviderContact(token, id, body);
      toast.success("Contact logged.");
      setLogOpen(false);
      resetLogForm();
      fetchContacts();
    } catch {
      // apiFetch already showed a toast
    } finally {
      setLogSubmitting(false);
    }
  }

  // ── Delete contact ─────────────────────────────────────────────
  async function handleDeleteContact(contactId: string) {
    setDeletingId(contactId);
    try {
      await deleteProviderContact(token, contactId);
      toast.success("Contact entry removed.");
      fetchContacts();
    } catch {
      // apiFetch already showed a toast
    } finally {
      setDeletingId(null);
    }
  }

  // ── Loading / error gates ───────────────────────────────────────
  if (loading) return <DetailSkeleton />;
  if (error) return <ErrorState message={error} onRetry={fetchProvider} />;
  if (!provider) return null;

  // ── Render ──────────────────────────────────────────────────
  return (
    <div className="space-y-6 max-w-4xl mx-auto">
      {/* Back link */}
      <div>
        <Button variant="ghost" size="sm" asChild>
          <Link href="/app/providers" className="flex items-center gap-1.5">
            <ArrowLeft className="h-4 w-4" />
            Back to Providers
          </Link>
        </Button>
      </div>

      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-center gap-3 min-w-0">
          <Building2 className="h-7 w-7 shrink-0 text-brand-600" aria-hidden="true" />
          <h2 className="text-2xl font-bold tracking-tight truncate">
            {provider.name}
          </h2>
        </div>
        <Button
          size="sm"
          variant="outline"
          onClick={openEdit}
          aria-label="Edit provider details"
          className="shrink-0"
        >
          <Pencil className="mr-1.5 h-3.5 w-3.5" />
          Edit
        </Button>
      </div>

      {/* Edit provider dialog */}
      <Dialog
        open={editOpen}
        onOpenChange={(v) => {
          setEditOpen(v);
        }}
      >
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Edit Provider</DialogTitle>
          </DialogHeader>
          <form onSubmit={handleEditSave} className="space-y-4 py-2">
            <div className="space-y-1.5">
              <Label htmlFor="editProviderName">
                Name <span className="text-red-500" aria-hidden="true">*</span>
              </Label>
              <Input
                id="editProviderName"
                value={editForm.name ?? ""}
                onChange={(e) =>
                  setEditForm((f) => ({ ...f, name: e.target.value }))
                }
                disabled={editSaving}
                required
                autoFocus
              />
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="editContactName">
                Contact name{" "}
                <span className="text-zinc-400 font-normal">(optional)</span>
              </Label>
              <Input
                id="editContactName"
                placeholder="Relationship manager name"
                value={editForm.contact_name ?? ""}
                onChange={(e) =>
                  setEditForm((f) => ({ ...f, contact_name: e.target.value }))
                }
                disabled={editSaving}
              />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label htmlFor="editContactEmail">
                  Email{" "}
                  <span className="text-zinc-400 font-normal">(optional)</span>
                </Label>
                <Input
                  id="editContactEmail"
                  type="email"
                  placeholder="contact@insurer.com"
                  value={editForm.contact_email ?? ""}
                  onChange={(e) =>
                    setEditForm((f) => ({
                      ...f,
                      contact_email: e.target.value,
                    }))
                  }
                  disabled={editSaving}
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="editContactPhone">
                  Phone{" "}
                  <span className="text-zinc-400 font-normal">(optional)</span>
                </Label>
                <Input
                  id="editContactPhone"
                  type="tel"
                  placeholder="+91 98765 43210"
                  value={editForm.contact_phone ?? ""}
                  onChange={(e) =>
                    setEditForm((f) => ({
                      ...f,
                      contact_phone: e.target.value,
                    }))
                  }
                  disabled={editSaving}
                />
              </div>
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="editNotes">
                Notes{" "}
                <span className="text-zinc-400 font-normal">(optional)</span>
              </Label>
              <textarea
                id="editNotes"
                rows={3}
                placeholder="Any notes about this insurer or broker…"
                value={editForm.notes ?? ""}
                onChange={(e) =>
                  setEditForm((f) => ({ ...f, notes: e.target.value }))
                }
                disabled={editSaving}
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
                onClick={() => setEditOpen(false)}
                disabled={editSaving}
              >
                Cancel
              </Button>
              <Button
                type="submit"
                disabled={editSaving || !editForm.name?.trim()}
                className="bg-brand-600 hover:bg-brand-600/90 text-white"
              >
                {editSaving ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Saving…
                  </>
                ) : (
                  "Save changes"
                )}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* Details card */}
      <Card>
        <CardHeader>
          <CardTitle className="text-sm font-semibold">Contact Details</CardTitle>
        </CardHeader>
        <CardContent>
          {provider.contact_name ||
          provider.contact_email ||
          provider.contact_phone ? (
            <dl className="space-y-3">
              {provider.contact_name && (
                <div className="flex items-center gap-3">
                  <User
                    className="h-4 w-4 shrink-0 text-zinc-400"
                    aria-hidden="true"
                  />
                  <div>
                    <dt className="sr-only">Contact name</dt>
                    <dd className="text-sm font-medium">
                      {provider.contact_name}
                    </dd>
                  </div>
                </div>
              )}
              {provider.contact_email && (
                <div className="flex items-center gap-3">
                  <Mail
                    className="h-4 w-4 shrink-0 text-zinc-400"
                    aria-hidden="true"
                  />
                  <div>
                    <dt className="sr-only">Email</dt>
                    <dd className="text-sm">
                      <a
                        href={`mailto:${provider.contact_email}`}
                        className="text-brand-600 hover:underline dark:text-brand-400"
                        aria-label={`Email ${provider.contact_name ?? provider.name} at ${provider.contact_email}`}
                      >
                        {provider.contact_email}
                      </a>
                    </dd>
                  </div>
                </div>
              )}
              {provider.contact_phone && (
                <div className="flex items-center gap-3">
                  <Phone
                    className="h-4 w-4 shrink-0 text-zinc-400"
                    aria-hidden="true"
                  />
                  <div>
                    <dt className="sr-only">Phone</dt>
                    <dd className="text-sm">
                      <a
                        href={`tel:${provider.contact_phone}`}
                        className="text-brand-600 hover:underline dark:text-brand-400"
                        aria-label={`Call ${provider.contact_name ?? provider.name} at ${provider.contact_phone}`}
                      >
                        {provider.contact_phone}
                      </a>
                    </dd>
                  </div>
                </div>
              )}
            </dl>
          ) : (
            <p className="text-sm text-zinc-400 dark:text-zinc-500">
              No contact details on record.{" "}
              <button
                type="button"
                onClick={openEdit}
                className="text-brand-600 underline-offset-2 hover:underline dark:text-brand-400"
              >
                Add them now
              </button>
            </p>
          )}
        </CardContent>
      </Card>

      {/* Contact log card */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between gap-4 pb-3">
          <CardTitle className="text-sm font-semibold flex items-center gap-2">
            <MessageSquare className="h-4 w-4 text-brand-600" aria-hidden="true" />
            Contact Log
          </CardTitle>
          <Button
            size="sm"
            variant="outline"
            onClick={() => setLogOpen(true)}
            aria-label="Log a new contact entry"
          >
            <Plus className="mr-1.5 h-4 w-4" />
            Log contact
          </Button>
        </CardHeader>
        <CardContent>
          {contactsLoading ? (
            <ContactsSkeleton />
          ) : contactsError ? (
            <ContactsError
              message={contactsError}
              onRetry={fetchContacts}
            />
          ) : contacts.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-10 text-center">
              <MessageSquare className="mb-2 h-8 w-8 text-zinc-300 dark:text-zinc-600" />
              <p className="text-sm font-medium text-zinc-500">
                No contact history yet.
              </p>
              <p className="mt-0.5 text-xs text-zinc-400">
                Log a call, email, meeting, or note to track interactions.
              </p>
              <Button
                size="sm"
                variant="outline"
                className="mt-4"
                onClick={() => setLogOpen(true)}
              >
                <Plus className="mr-1.5 h-4 w-4" />
                Log first contact
              </Button>
            </div>
          ) : (
            <ol className="relative border-l border-zinc-200 dark:border-zinc-800 pl-5 space-y-5">
              {contacts.map((entry) => (
                <li key={entry.id} className="relative">
                  {/* Timeline dot */}
                  <span
                    className="absolute -left-[1.4375rem] top-0.5 flex h-5 w-5 items-center justify-center rounded-full bg-white ring-2 ring-zinc-200 dark:bg-zinc-900 dark:ring-zinc-800"
                    aria-hidden="true"
                  >
                    {kindIcon(entry.kind)}
                  </span>

                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="text-xs font-semibold uppercase tracking-wide text-brand-600 dark:text-brand-400">
                          {entry.kind}
                        </span>
                        <span className="text-xs text-zinc-400">
                          {formatDate(entry.contacted_at)}
                        </span>
                      </div>
                      {entry.subject && (
                        <p className="mt-0.5 text-sm font-semibold text-zinc-900 dark:text-zinc-100">
                          {entry.subject}
                        </p>
                      )}
                      {entry.note && (
                        <p className="mt-0.5 text-sm text-zinc-600 dark:text-zinc-400 whitespace-pre-wrap">
                          {entry.note}
                        </p>
                      )}
                      {!entry.subject && !entry.note && (
                        <p className="mt-0.5 text-xs text-zinc-400 italic">
                          No details recorded.
                        </p>
                      )}
                    </div>

                    <Button
                      size="sm"
                      variant="ghost"
                      aria-label="Delete this contact entry"
                      disabled={deletingId === entry.id}
                      onClick={() => handleDeleteContact(entry.id)}
                      className="shrink-0 h-7 w-7 p-0 text-red-400 hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-950/30"
                    >
                      {deletingId === entry.id ? (
                        <Loader2 className="h-3.5 w-3.5 animate-spin" />
                      ) : (
                        <Trash2 className="h-3.5 w-3.5" />
                      )}
                    </Button>
                  </div>
                </li>
              ))}
            </ol>
          )}
        </CardContent>
      </Card>

      {/* Log contact dialog */}
      <Dialog
        open={logOpen}
        onOpenChange={(v) => {
          setLogOpen(v);
          if (!v) resetLogForm();
        }}
      >
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Log Contact</DialogTitle>
          </DialogHeader>
          <form onSubmit={handleLogSubmit} className="space-y-4 py-2">
            <div className="space-y-1.5">
              <Label htmlFor="logKind">
                Type <span className="text-red-500" aria-hidden="true">*</span>
              </Label>
              <Select
                value={logKind}
                onValueChange={(v) => setLogKind(v as ContactKind)}
              >
                <SelectTrigger id="logKind" className="w-full">
                  <SelectValue placeholder="Select type" />
                </SelectTrigger>
                <SelectContent>
                  {KIND_OPTIONS.map((opt) => (
                    <SelectItem key={opt.value} value={opt.value}>
                      {opt.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="logSubject">
                Subject{" "}
                <span className="text-zinc-400 font-normal">(optional)</span>
              </Label>
              <Input
                id="logSubject"
                placeholder="e.g. Renewal discussion, claim follow-up"
                value={logSubject}
                onChange={(e) => setLogSubject(e.target.value)}
                disabled={logSubmitting}
              />
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="logNote">
                Note{" "}
                <span className="text-zinc-400 font-normal">(optional)</span>
              </Label>
              <textarea
                id="logNote"
                rows={3}
                placeholder="What was discussed or decided…"
                value={logNote}
                onChange={(e) => setLogNote(e.target.value)}
                disabled={logSubmitting}
                className={cn(
                  "w-full rounded-md border border-zinc-200 bg-transparent px-3 py-2 text-sm",
                  "placeholder:text-zinc-400 focus:outline-none focus:ring-2 focus:ring-brand-600",
                  "dark:border-zinc-800 dark:text-zinc-100 dark:placeholder:text-zinc-600",
                  "resize-none disabled:cursor-not-allowed disabled:opacity-50"
                )}
              />
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="logDate">Date</Label>
              <Input
                id="logDate"
                type="date"
                value={logDate}
                onChange={(e) => setLogDate(e.target.value)}
                disabled={logSubmitting}
                max={todayISO()}
              />
            </div>

            <DialogFooter>
              <Button
                type="button"
                variant="outline"
                onClick={() => {
                  setLogOpen(false);
                  resetLogForm();
                }}
                disabled={logSubmitting}
              >
                Cancel
              </Button>
              <Button
                type="submit"
                disabled={logSubmitting}
                className="bg-brand-600 hover:bg-brand-600/90 text-white"
              >
                {logSubmitting ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Saving…
                  </>
                ) : (
                  "Log contact"
                )}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}

// ── Sub-components ───────────────────────────────────────────────────
function DetailSkeleton() {
  return (
    <div className="space-y-6 max-w-4xl mx-auto">
      <Skeleton className="h-8 w-32" />
      <div className="flex items-center gap-3">
        <Skeleton className="h-7 w-7 rounded-full" />
        <Skeleton className="h-8 w-64" />
      </div>
      <Card>
        <CardHeader>
          <Skeleton className="h-4 w-32" />
        </CardHeader>
        <CardContent className="space-y-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="flex items-center gap-3">
              <Skeleton className="h-4 w-4 rounded-full" />
              <Skeleton className="h-4 w-48" />
            </div>
          ))}
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <Skeleton className="h-4 w-32" />
        </CardHeader>
        <CardContent>
          <ContactsSkeleton />
        </CardContent>
      </Card>
    </div>
  );
}

function ContactsSkeleton() {
  return (
    <div className="space-y-4 pl-5">
      {Array.from({ length: 3 }).map((_, i) => (
        <div key={i} className="space-y-1.5">
          <div className="flex items-center gap-2">
            <Skeleton className="h-3 w-12" />
            <Skeleton className="h-3 w-20" />
          </div>
          <Skeleton className="h-4 w-56" />
          <Skeleton className="h-3 w-full" />
        </div>
      ))}
    </div>
  );
}

function ContactsError({
  message,
  onRetry,
}: {
  message: string;
  onRetry: () => void;
}) {
  return (
    <div className="flex flex-col items-center justify-center py-8 text-center">
      <AlertTriangle className="mb-2 h-7 w-7 text-red-400" />
      <p className="text-sm font-medium">Failed to load contact log</p>
      <p className="mt-0.5 text-xs text-zinc-500">{message}</p>
      <Button size="sm" variant="outline" className="mt-3" onClick={onRetry}>
        Retry
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
    <div className="flex flex-col items-center justify-center py-24 text-center">
      <AlertTriangle className="mb-3 h-10 w-10 text-red-400" />
      <h3 className="font-semibold">Failed to load provider</h3>
      <p className="mt-1 text-sm text-zinc-500">{message}</p>
      <Button size="sm" variant="outline" className="mt-4" onClick={onRetry}>
        Retry
      </Button>
    </div>
  );
}
