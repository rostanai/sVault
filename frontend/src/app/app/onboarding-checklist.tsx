"use client";

import Link from "next/link";
import { CheckCircle2, Circle, X } from "lucide-react";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import type { OnboardingStatus, OnboardingStep } from "@/lib/api";

interface OnboardingChecklistProps {
  status: OnboardingStatus;
  /** When provided, renders a dismiss (X) button that calls this handler. */
  onDismiss?: () => void;
}

export function OnboardingChecklist({ status, onDismiss }: OnboardingChecklistProps) {
  if (status.complete) return null;

  const progressPct =
    status.total > 0
      ? Math.round((status.completed_count / status.total) * 100)
      : 0;

  return (
    <Card
      role="region"
      aria-label="Onboarding checklist"
      className="border-brand-200 bg-brand-50/40 dark:border-brand-900 dark:bg-brand-950/20"
    >
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between gap-4">
          <div>
            <h3 className="text-sm font-semibold leading-tight">
              Get started with sVault
            </h3>
            <p className="mt-0.5 text-xs text-zinc-500 dark:text-zinc-400">
              {status.completed_count} of {status.total} done
            </p>
          </div>
          <div className="flex shrink-0 items-center gap-2">
            <span
              className="text-xs font-medium text-brand-600 dark:text-brand-400"
              aria-hidden="true"
            >
              {progressPct}%
            </span>
            {onDismiss && (
              <button
                type="button"
                onClick={onDismiss}
                aria-label="Dismiss the getting-started checklist"
                title="Dismiss"
                className="rounded-md p-1 text-zinc-400 hover:bg-zinc-200/60 hover:text-zinc-700 dark:hover:bg-zinc-700/60 dark:hover:text-zinc-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
              >
                <X className="h-4 w-4" />
              </button>
            )}
          </div>
        </div>

        {/* Progress bar */}
        <div
          role="progressbar"
          aria-valuenow={status.completed_count}
          aria-valuemin={0}
          aria-valuemax={status.total}
          aria-label={`${status.completed_count} of ${status.total} onboarding steps complete`}
          className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-zinc-200 dark:bg-zinc-700"
        >
          <div
            className="h-full rounded-full bg-brand-600 transition-all duration-500"
            style={{ width: `${progressPct}%` }}
          />
        </div>
      </CardHeader>

      <CardContent className="pt-0">
        <ul className="space-y-3" aria-label="Onboarding steps">
          {status.steps.map((step: OnboardingStep) => (
            <li
              key={step.key}
              className="flex items-start gap-3"
            >
              {/* Status icon */}
              <span
                className="mt-0.5 shrink-0"
                aria-hidden="true"
              >
                {step.done ? (
                  <CheckCircle2 className="h-4 w-4 text-emerald-500" />
                ) : (
                  <Circle className="h-4 w-4 text-zinc-300 dark:text-zinc-600" />
                )}
              </span>

              {/* Step content */}
              <div className="min-w-0 flex-1">
                <span
                  className={
                    step.done
                      ? "text-sm font-medium text-zinc-400 line-through dark:text-zinc-500"
                      : "text-sm font-medium text-zinc-800 dark:text-zinc-200"
                  }
                >
                  {step.label}
                </span>
                {step.description && (
                  <p className="mt-0.5 text-xs text-zinc-400 dark:text-zinc-500">
                    {step.description}
                  </p>
                )}
              </div>

              {/* Action link — only for incomplete steps */}
              {!step.done && (
                <Link
                  href={step.href}
                  aria-label={`Do: ${step.label}`}
                  className="shrink-0 text-xs font-medium text-brand-600 hover:text-brand-700 hover:underline dark:text-brand-400 dark:hover:text-brand-300 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 rounded"
                >
                  Do this &rarr;
                </Link>
              )}
            </li>
          ))}
        </ul>
      </CardContent>
    </Card>
  );
}
