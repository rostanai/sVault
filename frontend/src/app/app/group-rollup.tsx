"use client";

import { Network, Building2 } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableFooter,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { formatINR, cn } from "@/lib/utils";
import type { GroupDashboardResponse } from "@/lib/api";

interface GroupRollupProps {
  /** undefined = still loading; null = failed/hidden; data = loaded */
  group: GroupDashboardResponse | null | undefined;
}

/**
 * Consolidated group breakdown card — shown only when the tenant has
 * more than one organisation (i.e. parent + subsidiaries).
 *
 * Visibility rules:
 *   undefined → skeleton (loading)
 *   null      → render nothing (error or not applicable)
 *   data with by_org.length <= 1 → render nothing (single-org tenant)
 *   data with by_org.length > 1  → render the card
 */
export function GroupRollup({ group }: GroupRollupProps) {
  // Loading state: show a minimal skeleton placeholder
  if (group === undefined) {
    return (
      <Card aria-busy="true" aria-label="Loading group breakdown">
        <CardHeader className="flex flex-row items-center gap-2 pb-2">
          <Network className="h-4 w-4 text-brand-600" aria-hidden="true" />
          <Skeleton className="h-4 w-40" />
        </CardHeader>
        <CardContent>
          <Skeleton className="h-28 w-full" />
        </CardContent>
      </Card>
    );
  }

  // null = fetch failed or feature hidden; single-org = nothing to roll up
  if (!group || group.by_org.length <= 1) {
    return null;
  }

  const { totals, by_org } = group;

  return (
    <Card>
      <CardHeader className="flex flex-row items-center gap-2 pb-3">
        <Network
          className="h-4 w-4 text-brand-600 shrink-0"
          aria-hidden="true"
        />
        <CardTitle className="text-sm font-semibold">
          Group Breakdown
        </CardTitle>
        <span className="ml-auto text-xs text-zinc-400 dark:text-zinc-500">
          {by_org.length} organisations
        </span>
      </CardHeader>

      <CardContent className="p-0">
        <Table aria-label="Consolidated group dashboard by organisation">
          <TableHeader>
            <TableRow>
              <TableHead className="pl-6">
                <span className="flex items-center gap-1.5">
                  <Building2
                    className="h-3.5 w-3.5 text-zinc-400"
                    aria-hidden="true"
                  />
                  Organisation
                </span>
              </TableHead>
              <TableHead className="text-right tabular-nums">Policies</TableHead>
              <TableHead className="text-right tabular-nums">
                Sum Insured
              </TableHead>
              <TableHead className="text-right tabular-nums">
                Annual Premium
              </TableHead>
              <TableHead className="text-right">Expiring (30d)</TableHead>
            </TableRow>
          </TableHeader>

          <TableBody>
            {by_org.map((org) => (
              <TableRow
                key={org.org_id}
                className={cn(
                  org.expiring_30 > 0 &&
                    "bg-amber-50/60 dark:bg-amber-950/20"
                )}
              >
                <TableCell className="pl-6 font-medium">
                  {org.org_name}
                </TableCell>
                <TableCell className="text-right tabular-nums text-zinc-700 dark:text-zinc-300">
                  {org.policies}
                </TableCell>
                <TableCell className="text-right tabular-nums text-zinc-700 dark:text-zinc-300">
                  {formatINR(org.sum_insured_inr)}
                </TableCell>
                <TableCell className="text-right tabular-nums text-zinc-700 dark:text-zinc-300">
                  {formatINR(org.premium_inr)}
                </TableCell>
                <TableCell className="text-right">
                  {org.expiring_30 > 0 ? (
                    <Badge
                      variant="warning"
                      className="tabular-nums"
                      aria-label={`${org.expiring_30} policies expiring within 30 days`}
                    >
                      {org.expiring_30}
                    </Badge>
                  ) : (
                    <span className="text-zinc-400 dark:text-zinc-600">—</span>
                  )}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>

          <TableFooter>
            <TableRow className="font-semibold text-zinc-900 dark:text-zinc-100 bg-zinc-50 dark:bg-zinc-900">
              <TableCell className="pl-6">Group Total</TableCell>
              <TableCell className="text-right tabular-nums">
                {totals.policies}
              </TableCell>
              <TableCell className="text-right tabular-nums">
                {formatINR(totals.sum_insured_inr)}
              </TableCell>
              <TableCell className="text-right tabular-nums">
                {formatINR(totals.premium_inr)}
              </TableCell>
              <TableCell className="text-right text-zinc-400 dark:text-zinc-500">
                —
              </TableCell>
            </TableRow>
          </TableFooter>
        </Table>
      </CardContent>
    </Card>
  );
}
