"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import {
  getPolicy,
  listDocuments,
  getDocumentUploadUrl,
  uploadFileToStorage,
  recordDocument,
  deleteDocument,
  ingestDocument,
  type PolicyRead,
  type DocumentRead,
} from "@/lib/api";
import {
  formatDate,
  formatINR,
  daysLeftVariant,
  categorylabel,
  statusLabel,
} from "@/lib/utils";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import {
  ArrowLeft,
  AlertTriangle,
  Upload,
  Loader2,
  FileText,
  Download,
  Trash2,
  Paperclip,
  Sparkles,
} from "lucide-react";
import { toast } from "sonner";

const MAX_BYTES = 20 * 1024 * 1024; // 20 MB
const ALLOWED_TYPES = [
  "application/pdf",
  "image/png",
  "image/jpeg",
  "image/webp",
];
const ALLOWED_EXTS = ".pdf,.png,.jpg,.jpeg,.webp";

function formatBytes(bytes: number | null | undefined): string {
  if (bytes == null) return "—";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

interface Props {
  id: string;
  token: string;
}

export default function PolicyDetailClient({ id, token }: Props) {
  const [policy, setPolicy] = useState<PolicyRead | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!token) {
      setError("No active session.");
      setLoading(false);
      return;
    }
    getPolicy(token, id)
      .then(setPolicy)
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false));
  }, [id, token]);

  if (loading) return <DetailSkeleton />;
  if (error) return <ErrorState message={error} />;
  if (!policy) return null;

  const daysLeft = policy.expiry_date
    ? Math.ceil(
        (new Date(policy.expiry_date).getTime() - Date.now()) / 86400000
      )
    : null;

  const fields: { label: string; value: string }[] = [
    { label: "Policy Number", value: policy.policy_number ?? "—" },
    { label: "Category", value: categorylabel(policy.category) },
    { label: "Status", value: statusLabel(policy.status) },
    { label: "Sum Insured", value: formatINR(policy.sum_insured_inr) },
    { label: "Annual Premium", value: formatINR(policy.premium_inr) },
    { label: "GST", value: formatINR(policy.gst_inr) },
    { label: "Inception Date", value: formatDate(policy.inception_date) },
    { label: "Expiry Date", value: formatDate(policy.expiry_date) },
    { label: "Renewal Date", value: formatDate(policy.renewal_date) },
    { label: "Created", value: formatDate(policy.created_at) },
  ];

  return (
    <div className="space-y-6 max-w-2xl">
      {/* Back */}
      <div>
        <Button variant="ghost" size="sm" asChild>
          <Link href="/app/policies" className="flex items-center gap-1.5">
            <ArrowLeft className="h-4 w-4" />
            Back to Policies
          </Link>
        </Button>
      </div>

      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">{policy.title}</h2>
          <p className="text-sm text-zinc-500 dark:text-zinc-400">
            {categorylabel(policy.category)}
          </p>
        </div>
        <div className="flex flex-col items-end gap-1.5 shrink-0">
          <Badge
            variant={
              policy.status === "active"
                ? "success"
                : policy.status === "expiring"
                ? "warning"
                : policy.status === "lapsed" || policy.status === "cancelled"
                ? "destructive"
                : "secondary"
            }
          >
            {statusLabel(policy.status)}
          </Badge>
          {daysLeft != null && (
            <Badge variant={daysLeftVariant(daysLeft)} className="text-xs">
              {daysLeft < 0
                ? `Expired ${Math.abs(daysLeft)}d ago`
                : `${daysLeft}d left`}
            </Badge>
          )}
        </div>
      </div>

      {/* Details card */}
      <Card>
        <CardHeader>
          <CardTitle className="text-sm font-semibold">Policy Details</CardTitle>
        </CardHeader>
        <CardContent>
          <dl className="grid grid-cols-1 gap-x-8 gap-y-4 sm:grid-cols-2">
            {fields.map(({ label, value }) => (
              <div key={label}>
                <dt className="text-xs font-medium uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
                  {label}
                </dt>
                <dd className="mt-1 text-sm font-medium">{value}</dd>
              </div>
            ))}
          </dl>
        </CardContent>
      </Card>

      {/* Documents */}
      <DocumentsCard policyId={id} token={token} />

      {/* Alert Schedule stub */}
      <Card>
        <CardHeader>
          <CardTitle className="text-sm font-semibold">Alert Schedule</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-zinc-400">
            Alert configuration coming soon.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}

// ── Documents card ────────────────────────────────────────────────────────

function DocumentsCard({
  policyId,
  token,
}: {
  policyId: string;
  token: string;
}) {
  const [docs, setDocs] = useState<DocumentRead[]>([]);
  const [docsLoading, setDocsLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [indexingId, setIndexingId] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  function loadDocs() {
    setDocsLoading(true);
    listDocuments(token, policyId)
      .then(setDocs)
      .catch((err: Error) => {
        toast.error("Failed to load documents", { description: err.message });
      })
      .finally(() => setDocsLoading(false));
  }

  useEffect(() => {
    if (token) loadDocs();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [policyId, token]);

  async function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;

    // Reset the input so the same file can be re-selected after an error.
    e.target.value = "";

    // Client-side validation
    if (!ALLOWED_TYPES.includes(file.type)) {
      toast.error("Unsupported file type.", {
        description: "Please upload a PDF, PNG, JPG, or WebP.",
      });
      return;
    }
    if (file.size > MAX_BYTES) {
      toast.error("File too large.", {
        description: "Maximum file size is 20 MB.",
      });
      return;
    }

    setUploading(true);
    try {
      // Step 1 — get a signed PUT URL from the backend.
      const { upload_url, storage_path } = await getDocumentUploadUrl(
        token,
        policyId,
        { file_name: file.name, content_type: file.type }
      );

      // Step 2 — PUT the raw bytes directly to Supabase Storage.
      await uploadFileToStorage(upload_url, file);

      // Step 3 — record the document in the DB so the backend creates the row.
      await recordDocument(token, policyId, {
        storage_path,
        file_name: file.name,
        content_type: file.type,
        size_bytes: file.size,
        doc_type: "policy",
      });

      toast.success(`"${file.name}" uploaded.`);
      loadDocs();
    } catch (err: unknown) {
      // apiFetch already shows a toast for backend errors; only catch storage errors here.
      const msg = err instanceof Error ? err.message : String(err);
      if (msg.startsWith("Storage upload failed")) {
        toast.error("Upload failed.", { description: msg });
      }
      // Otherwise apiFetch already toasted.
    } finally {
      setUploading(false);
    }
  }

  async function handleDelete(doc: DocumentRead) {
    setDeletingId(doc.id);
    try {
      await deleteDocument(token, doc.id);
      toast.success(`"${doc.file_name}" deleted.`);
      loadDocs();
    } catch {
      // apiFetch already showed a toast.
    } finally {
      setDeletingId(null);
    }
  }

  async function handleIndex(doc: DocumentRead) {
    setIndexingId(doc.id);
    try {
      const res = await ingestDocument(token, policyId, doc.id);
      if (res.chunks === 0) {
        toast.info("No extractable text found.", {
          description: `"${doc.file_name}" may not be a text-based PDF.`,
        });
      } else {
        toast.success(`Indexed ${res.chunks} chunks for AI search.`, {
          description: `"${doc.file_name}" is now searchable via Ask sVault.`,
        });
      }
    } catch {
      // apiFetch already showed a toast (including 402 entitlement_required).
    } finally {
      setIndexingId(null);
    }
  }

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between gap-4 pb-3">
        <CardTitle className="text-sm font-semibold">Documents</CardTitle>
        <div>
          {/* Hidden file input */}
          <input
            ref={fileRef}
            type="file"
            accept={ALLOWED_EXTS}
            className="sr-only"
            aria-label="Upload policy document"
            onChange={handleFileChange}
            disabled={uploading}
          />
          <Button
            size="sm"
            variant="outline"
            disabled={uploading}
            onClick={() => fileRef.current?.click()}
          >
            {uploading ? (
              <>
                <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />
                Uploading…
              </>
            ) : (
              <>
                <Upload className="mr-1.5 h-4 w-4" />
                Upload
              </>
            )}
          </Button>
        </div>
      </CardHeader>

      <CardContent>
        {docsLoading ? (
          <div className="space-y-2">
            {[1, 2].map((i) => (
              <div key={i} className="flex items-center gap-3">
                <Skeleton className="h-8 w-8 rounded" />
                <div className="flex-1 space-y-1">
                  <Skeleton className="h-3 w-48" />
                  <Skeleton className="h-3 w-24" />
                </div>
              </div>
            ))}
          </div>
        ) : docs.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-8 text-center">
            <Paperclip className="mb-2 h-7 w-7 text-zinc-300" />
            <p className="text-sm text-zinc-500">No documents attached.</p>
            <p className="text-xs text-zinc-400 mt-0.5">
              Upload a PDF or image (max 20 MB).
            </p>
          </div>
        ) : (
          <ul className="divide-y divide-zinc-100 dark:divide-zinc-800">
            {docs.map((doc) => (
              <li key={doc.id} className="flex items-center gap-3 py-2.5">
                <FileText className="h-5 w-5 shrink-0 text-zinc-400" />
                <div className="flex-1 min-w-0">
                  <p
                    className="truncate text-sm font-medium"
                    title={doc.file_name}
                  >
                    {doc.file_name}
                  </p>
                  <p className="text-xs text-zinc-400">
                    {formatBytes(doc.size_bytes)} &middot; v{doc.version} &middot;{" "}
                    {formatDate(doc.created_at)}
                  </p>
                </div>
                <div className="flex items-center gap-1.5 shrink-0">
                  <Button
                    size="sm"
                    variant="ghost"
                    aria-label={`Index ${doc.file_name} for AI search`}
                    title="Index for AI"
                    disabled={indexingId === doc.id}
                    onClick={() => handleIndex(doc)}
                    className="text-zinc-500 hover:text-brand-600 hover:bg-brand-600/10 dark:hover:bg-brand-600/10"
                  >
                    {indexingId === doc.id ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <Sparkles className="h-4 w-4" />
                    )}
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    asChild
                    aria-label={`Download ${doc.file_name}`}
                  >
                    <a
                      href={doc.download_url}
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      <Download className="h-4 w-4" />
                    </a>
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    aria-label={`Delete ${doc.file_name}`}
                    disabled={deletingId === doc.id}
                    onClick={() => handleDelete(doc)}
                    className="text-red-500 hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-950/30"
                  >
                    {deletingId === doc.id ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <Trash2 className="h-4 w-4" />
                    )}
                  </Button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}

// ── Skeleton / Error helpers ───────────────────────────────────────────

function DetailSkeleton() {
  return (
    <div className="space-y-6 max-w-2xl">
      <Skeleton className="h-8 w-20" />
      <div className="space-y-2">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-4 w-32" />
      </div>
      <Card>
        <CardHeader>
          <Skeleton className="h-4 w-32" />
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 gap-4">
            {Array.from({ length: 8 }).map((_, i) => (
              <div key={i} className="space-y-1">
                <Skeleton className="h-3 w-20" />
                <Skeleton className="h-4 w-32" />
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
      <h3 className="font-semibold">Failed to load policy</h3>
      <p className="mt-1 text-sm text-zinc-500">{message}</p>
    </div>
  );
}
