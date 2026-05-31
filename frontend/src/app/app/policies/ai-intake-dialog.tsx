"use client";

import { useRef, useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { extractPolicyFromDocument, type PolicyExtraction } from "@/lib/api";
import { Sparkles, Loader2, FileText, UploadCloud, X } from "lucide-react";
import { cn } from "@/lib/utils";

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  token: string;
  /** Called when extraction succeeds and the user should proceed to review */
  onExtracted: (extraction: PolicyExtraction) => void;
  /** Called when the doc is scanned (0 chars) and the user clicks "Enter manually" */
  onEnterManually: () => void;
}

const MAX_BYTES = 20 * 1024 * 1024; // 20 MB

export default function AiIntakeDialog({
  open,
  onOpenChange,
  token,
  onExtracted,
  onEnterManually,
}: Props) {
  const fileRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [extracting, setExtracting] = useState(false);
  const [scannedNote, setScannedNote] = useState<string | null>(null);

  // ── drag-and-drop state ──────────────────────────────────────────────
  const [dragOver, setDragOver] = useState(false);

  function resetState() {
    setFile(null);
    setExtracting(false);
    setScannedNote(null);
  }

  function handleClose(open: boolean) {
    if (!open) resetState();
    onOpenChange(open);
  }

  function pickFile(picked: File | null | undefined) {
    if (!picked) return;
    if (picked.type !== "application/pdf") {
      // silently ignore non-PDF — the accept attr is already ".pdf"
      return;
    }
    if (picked.size > MAX_BYTES) {
      // size guard — surface via the UI (no toast here; rely on visible message)
      return;
    }
    setScannedNote(null);
    setFile(picked);
  }

  function handleInputChange(e: React.ChangeEvent<HTMLInputElement>) {
    pickFile(e.target.files?.[0]);
    // reset so the same file can be re-selected if needed
    e.target.value = "";
  }

  function handleDrop(e: React.DragEvent<HTMLDivElement>) {
    e.preventDefault();
    setDragOver(false);
    pickFile(e.dataTransfer.files?.[0]);
  }

  async function handleExtract() {
    if (!file) return;
    setExtracting(true);
    setScannedNote(null);
    try {
      const extraction = await extractPolicyFromDocument(token, file);
      if (extraction.extracted_text_chars === 0) {
        // Scanned / unreadable — surface info and offer manual entry
        setScannedNote(
          extraction.notes ??
            "This document appears to be a scanned image. No machine-readable text could be found."
        );
      } else {
        onExtracted(extraction);
        handleClose(false);
      }
    } catch {
      // extractPolicyFromDocument already toasts on failure
    } finally {
      setExtracting(false);
    }
  }

  function handleEnterManually() {
    handleClose(false);
    onEnterManually();
  }

  const fileSizeMB = file ? (file.size / (1024 * 1024)).toFixed(1) : null;

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Sparkles className="h-5 w-5 text-brand-600" aria-hidden="true" />
            AI Policy Intake
          </DialogTitle>
        </DialogHeader>

        <div className="space-y-4 py-2">
          {/* Sub-copy */}
          <p className="text-sm text-zinc-500 dark:text-zinc-400">
            sVault AI reads your policy PDF and fills in the details for you to
            review.
          </p>

          {/* Drop zone / file picker */}
          <div
            role="button"
            tabIndex={0}
            aria-label="Click or drag a PDF here to select it"
            onClick={() => !extracting && fileRef.current?.click()}
            onKeyDown={(e) => {
              if ((e.key === "Enter" || e.key === " ") && !extracting)
                fileRef.current?.click();
            }}
            onDragOver={(e) => {
              e.preventDefault();
              setDragOver(true);
            }}
            onDragLeave={() => setDragOver(false)}
            onDrop={handleDrop}
            className={cn(
              "relative flex flex-col items-center justify-center rounded-xl border-2 border-dashed px-6 py-8 text-center transition-colors",
              "focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-600",
              dragOver
                ? "border-brand-600 bg-brand-600/5 dark:bg-brand-600/10"
                : file
                ? "border-brand-600/40 bg-brand-600/5 dark:bg-brand-600/10"
                : "border-zinc-200 hover:border-zinc-300 dark:border-zinc-700 dark:hover:border-zinc-600",
              extracting ? "cursor-not-allowed opacity-60" : "cursor-pointer"
            )}
          >
            {/* Hidden file input */}
            <input
              ref={fileRef}
              type="file"
              accept=".pdf"
              className="sr-only"
              aria-label="Select a PDF file"
              onChange={handleInputChange}
              disabled={extracting}
            />

            {file ? (
              <>
                <FileText
                  className="mb-2 h-8 w-8 text-brand-600"
                  aria-hidden="true"
                />
                <p className="text-sm font-medium truncate max-w-[240px]" title={file.name}>
                  {file.name}
                </p>
                <p className="mt-0.5 text-xs text-zinc-400">
                  {fileSizeMB} MB &middot; PDF
                </p>
                {!extracting && (
                  <button
                    type="button"
                    aria-label="Remove selected file"
                    onClick={(e) => {
                      e.stopPropagation();
                      setFile(null);
                      setScannedNote(null);
                    }}
                    className={cn(
                      "absolute right-3 top-3 rounded-full p-0.5",
                      "text-zinc-400 hover:text-zinc-700 dark:hover:text-zinc-200",
                      "focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-600"
                    )}
                  >
                    <X className="h-4 w-4" />
                  </button>
                )}
              </>
            ) : (
              <>
                <UploadCloud
                  className="mb-2 h-8 w-8 text-zinc-300 dark:text-zinc-600"
                  aria-hidden="true"
                />
                <p className="text-sm font-medium text-zinc-600 dark:text-zinc-400">
                  Drop your policy PDF here
                </p>
                <p className="mt-0.5 text-xs text-zinc-400">
                  or click to browse &middot; PDF only &middot; max 20 MB
                </p>
              </>
            )}
          </div>

          {/* Scanned-document info message */}
          {scannedNote && (
            <div
              role="alert"
              className={cn(
                "rounded-lg border border-blue-200 bg-blue-50 px-4 py-3 text-sm text-blue-800",
                "dark:border-blue-800 dark:bg-blue-950/40 dark:text-blue-300"
              )}
            >
              <p className="font-medium mb-1">Could not extract text</p>
              <p className="text-xs">{scannedNote}</p>
            </div>
          )}
        </div>

        <DialogFooter className="flex-col-reverse gap-2 sm:flex-row sm:gap-0">
          {scannedNote ? (
            <>
              <Button
                type="button"
                variant="outline"
                onClick={() => handleClose(false)}
              >
                Cancel
              </Button>
              <Button
                type="button"
                variant="default"
                className="bg-brand-600 hover:bg-brand-600/90"
                onClick={handleEnterManually}
              >
                Enter manually
              </Button>
            </>
          ) : (
            <>
              <Button
                type="button"
                variant="outline"
                onClick={() => handleClose(false)}
                disabled={extracting}
              >
                Cancel
              </Button>
              <Button
                type="button"
                disabled={!file || extracting}
                className="bg-brand-600 hover:bg-brand-600/90 text-white"
                onClick={handleExtract}
              >
                {extracting ? (
                  <>
                    <Loader2
                      className="mr-2 h-4 w-4 animate-spin"
                      aria-hidden="true"
                    />
                    Extracting…
                  </>
                ) : (
                  <>
                    <Sparkles
                      className="mr-2 h-4 w-4"
                      aria-hidden="true"
                    />
                    Extract with AI
                  </>
                )}
              </Button>
            </>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
