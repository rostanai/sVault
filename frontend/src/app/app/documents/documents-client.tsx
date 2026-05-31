"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import Link from "next/link";
import {
  getAllDocuments,
  type DocumentLibraryItem,
  type DocType,
} from "@/lib/api";
import { formatDate, categorylabel, cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import {
  FileText,
  Search,
  Download,
  Paperclip,
  AlertTriangle,
} from "lucide-react";

// ── Types ─────────────────────────────────────────────────────────────────────

interface Props {
  token: string;
}

type DocTypeFilter = DocType | "all";

// ── Constants ─────────────────────────────────────────────────────────────────

const DOC_TYPE_FILTERS: { value: DocTypeFilter; label: string }[] = [
  { value: "all", label: "All" },
  { value: "policy", label: "Policy" },
  { value: "schedule", label: "Schedule" },
  { value: "endorsement", label: "Endorsement" },
  { value: "invoice", label: "Invoice" },
  { value: "claim", label: "Claim" },
  { value: "other", label: "Other" },
];

const DEBOUNCE_MS = 350;

// ── Helpers ───────────────────────────────────────────────────────────────────

function formatBytes(bytes: number | null | undefined): string {
  if (bytes == null) return "—";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function docTypeBadgeVariant(
  docType: string
): "default" | "secondary" | "outline" | "warning" | "success" | "destructive" {
  switch (docType) {
    case "policy":
      return "default";
    case "schedule":
      return "secondary";
    case "endorsement":
      return "warning";
    case "invoice":
      return "success";
    case "claim":
      return "destructive";
    default:
      return "outline";
  }
}

function humanizeDocType(docType: string): string {
  return docType.charAt(0).toUpperCase() + docType.slice(1);
}

// ── Main component ────────────────────────────────────────────────────────────

export default function DocumentsClient({ token }: Props) {
  const [docs, setDocs] = useState<DocumentLibraryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [docTypeFilter, setDocTypeFilter] = useState<DocTypeFilter>("all");
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // ── Debounce search ───────────────────────────────────────────────────────

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      setDebouncedSearch(search);
    }, DEBOUNCE_MS);

    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [search]);

  // ── Fetch ─────────────────────────────────────────────────────────────────

  const fetchDocs = useCallback(() => {
    if (!token) {
      setError("No active session.");
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    getAllDocuments(token, {
      search: debouncedSearch.trim() || undefined,
      doc_type: docTypeFilter === "all" ? undefined : docTypeFilter,
      limit: 100,
    })
      .then((res) => {
        setDocs(Array.isArray(res) ? res : []);
      })
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false));
  }, [token, debouncedSearch, docTypeFilter]);

  useEffect(() => {
    fetchDocs();
  }, [fetchDocs]);

  // ── Derived state ─────────────────────────────────────────────────────────

  const hasActiveFilter =
    debouncedSearch.trim().length > 0 || docTypeFilter !== "all";
  const isSearching = debouncedSearch.trim().length > 0;

  // ── Render ────────────────────────────────────────────────────────────────

  return (
    <div className="space-y-5">
      {/* Page header */}
      <div>
        <h2 className="text-2xl font-bold tracking-tight flex items-center gap-2">
          <Paperclip className="h-6 w-6 text-brand-600" aria-hidden="true" />
          Document Library
        </h2>
        <p className="text-sm text-zinc-500 dark:text-zinc-400 mt-0.5">
          Search and download every policy document in one place.
        </p>
      </div>

      {/* Search + filters */}
      <div className="space-y-3">
        {/* Search input */}
        <div className="relative">
          <label htmlFor="doc-search" className="sr-only">
            Search documents
          </label>
          <Search
            className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-zinc-400 pointer-events-none"
            aria-hidden="true"
          />
          <Input
            id="doc-search"
            type="search"
            placeholder="Search by file name, policy, or text inside documents…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-9"
            aria-label="Search documents by file name, policy name, or document content"
          />
        </div>

        {/* Doc-type filter chips */}
        <div
          className="flex flex-wrap items-center gap-2"
          role="group"
          aria-label="Filter by document type"
        >
          {DOC_TYPE_FILTERS.map((f) => (
            <Button
              key={f.value}
              size="sm"
              variant={docTypeFilter === f.value ? "default" : "outline"}
              onClick={() => setDocTypeFilter(f.value)}
              aria-pressed={docTypeFilter === f.value}
              className={cn(
                "rounded-full h-7 px-3 text-xs font-medium",
                docTypeFilter === f.value
                  ? "bg-brand-600 text-white border-brand-600 hover:bg-brand-600/90"
                  : "text-zinc-600 dark:text-zinc-400"
              )}
            >
              {f.label}
            </Button>
          ))}
        </div>

        {/* Contextual hint when a text search is active */}
        {isSearching && (
          <p className="text-xs text-zinc-400 dark:text-zinc-500" role="note">
            Results may include matches found inside document text — that&apos;s
            why a snippet is shown below matching items.
          </p>
        )}
      </div>

      {/* Results */}
      {loading ? (
        <ListSkeleton />
      ) : error ? (
        <ErrorState message={error} onRetry={fetchDocs} />
      ) : docs.length === 0 ? (
        <EmptyState hasFilter={hasActiveFilter} isSearching={isSearching} />
      ) : (
        <DocList docs={docs} />
      )}
    </div>
  );
}

// ── Document list ─────────────────────────────────────────────────────────────

function DocList({ docs }: { docs: DocumentLibraryItem[] }) {
  return (
    <ul
      className="divide-y divide-zinc-100 dark:divide-zinc-800 rounded-xl border border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900 overflow-hidden"
      aria-label="Document list"
    >
      {docs.map((doc) => (
        <DocRow key={doc.id} doc={doc} />
      ))}
    </ul>
  );
}

// ── Single document row ───────────────────────────────────────────────────────

function DocRow({ doc }: { doc: DocumentLibraryItem }) {
  return (
    <li className="flex items-start gap-3 px-4 py-3.5 group hover:bg-zinc-50 dark:hover:bg-zinc-800/50 transition-colors">
      {/* File icon */}
      <FileText
        className="mt-0.5 h-5 w-5 shrink-0 text-zinc-400 group-hover:text-brand-600 dark:group-hover:text-brand-400 transition-colors"
        aria-hidden="true"
      />

      {/* Main content */}
      <div className="flex-1 min-w-0 space-y-0.5">
        {/* File name + doc-type badge */}
        <div className="flex flex-wrap items-center gap-2">
          <span
            className="text-sm font-medium truncate max-w-xs sm:max-w-md"
            title={doc.file_name}
          >
            {doc.file_name}
          </span>
          <Badge
            variant={docTypeBadgeVariant(doc.doc_type)}
            className="shrink-0 text-xs"
          >
            {humanizeDocType(doc.doc_type)}
          </Badge>
        </div>

        {/* Policy reference */}
        <p className="text-xs text-zinc-500 dark:text-zinc-400">
          <Link
            href={`/app/policies/${doc.policy_id}`}
            className="font-medium text-zinc-700 dark:text-zinc-300 hover:text-brand-600 dark:hover:text-brand-400 underline-offset-2 hover:underline transition-colors"
            aria-label={`View policy: ${doc.policy_title}`}
          >
            {doc.policy_title}
          </Link>
          <span className="mx-1.5 text-zinc-300 dark:text-zinc-600">&middot;</span>
          <span>{categorylabel(doc.policy_category)}</span>
        </p>

        {/* Size + date */}
        <p className="text-xs text-zinc-400 dark:text-zinc-500">
          {formatBytes(doc.size_bytes)}
          <span className="mx-1.5">&middot;</span>
          <time dateTime={doc.created_at}>{formatDate(doc.created_at)}</time>
        </p>

        {/* Content snippet (shown only when present — a text-search match) */}
        {doc.snippet != null && (
          <p
            className="mt-1.5 text-xs text-zinc-500 dark:text-zinc-400 italic leading-relaxed line-clamp-2 bg-zinc-50 dark:bg-zinc-800/60 rounded px-2 py-1"
            aria-label="Matching text found inside document"
          >
            &hellip;{doc.snippet}&hellip;
          </p>
        )}
      </div>

      {/* Download button */}
      <a
        href={doc.download_url}
        target="_blank"
        rel="noopener noreferrer"
        aria-label={`Download ${doc.file_name}`}
        className={cn(
          "shrink-0 mt-0.5 inline-flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-xs font-medium transition-colors",
          "text-zinc-500 hover:text-brand-600 hover:bg-brand-600/8",
          "dark:text-zinc-400 dark:hover:text-brand-400 dark:hover:bg-brand-600/10",
          "focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-600 focus-visible:ring-offset-1"
        )}
      >
        <Download className="h-3.5 w-3.5" aria-hidden="true" />
        <span className="hidden sm:inline">Download</span>
      </a>
    </li>
  );
}

// ── Loading skeleton ──────────────────────────────────────────────────────────

function ListSkeleton() {
  return (
    <div
      className="rounded-xl border border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900 divide-y divide-zinc-100 dark:divide-zinc-800"
      aria-label="Loading documents"
      aria-busy="true"
    >
      {Array.from({ length: 6 }).map((_, i) => (
        <div key={i} className="flex items-start gap-3 px-4 py-3.5">
          <Skeleton className="mt-0.5 h-5 w-5 rounded shrink-0" />
          <div className="flex-1 space-y-2">
            <div className="flex items-center gap-2">
              <Skeleton className="h-4 w-48" />
              <Skeleton className="h-5 w-16 rounded-full" />
            </div>
            <Skeleton className="h-3 w-64" />
            <Skeleton className="h-3 w-32" />
          </div>
          <Skeleton className="h-7 w-20 rounded-md shrink-0" />
        </div>
      ))}
    </div>
  );
}

// ── Empty state ───────────────────────────────────────────────────────────────

function EmptyState({
  hasFilter,
  isSearching,
}: {
  hasFilter: boolean;
  isSearching: boolean;
}) {
  return (
    <div className="flex flex-col items-center justify-center py-20 text-center rounded-xl border border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900">
      <Paperclip className="mb-3 h-10 w-10 text-zinc-300" aria-hidden="true" />
      <h3 className="font-semibold">
        {hasFilter ? "No documents match your search." : "No documents yet."}
      </h3>
      <p className="mt-1 text-sm text-zinc-400 max-w-xs">
        {isSearching
          ? "Try different keywords or clear the search to browse all documents."
          : hasFilter
          ? "Try selecting a different document type."
          : "Upload policy documents from any policy detail page and they will appear here."}
      </p>
    </div>
  );
}

// ── Error state ───────────────────────────────────────────────────────────────

function ErrorState({
  message,
  onRetry,
}: {
  message: string;
  onRetry: () => void;
}) {
  return (
    <div className="flex flex-col items-center justify-center py-20 text-center rounded-xl border border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900">
      <AlertTriangle
        className="mb-3 h-10 w-10 text-red-400"
        aria-hidden="true"
      />
      <h3 className="font-semibold">Failed to load documents</h3>
      <p className="mt-1 text-sm text-zinc-500">{message}</p>
      <Button size="sm" variant="outline" className="mt-4" onClick={onRetry}>
        Retry
      </Button>
    </div>
  );
}
