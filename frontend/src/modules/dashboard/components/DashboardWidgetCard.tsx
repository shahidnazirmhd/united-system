import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

import { EmptyState } from "@/components/common/EmptyState";
import { ErrorState } from "@/components/common/ErrorState";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

interface DashboardWidgetCardProps {
  title: string;
  icon?: LucideIcon;
  actions?: ReactNode;
  isLoading: boolean;
  isError: boolean;
  onRetry?: () => void;
  isEmpty?: boolean;
  emptyTitle?: string;
  emptyDescription?: string;
  className?: string;
  contentClassName?: string;
  children: ReactNode;
}

/**
 * The one generic wrapper every non-KPI Dashboard widget (chart, list,
 * table) renders its loading/error/empty states through — see `KpiCard`'s
 * own docstring for the identical reasoning applied to number cards. A
 * future widget only needs to supply `isLoading`/`isError`/`isEmpty` (from
 * its own TanStack Query hook) and its real content; it never re-implements
 * a skeleton, an `ErrorState`, or an `EmptyState` from scratch.
 */
export function DashboardWidgetCard({
  title,
  icon: Icon,
  actions,
  isLoading,
  isError,
  onRetry,
  isEmpty = false,
  emptyTitle = "Nothing to show yet",
  emptyDescription,
  className,
  contentClassName,
  children,
}: DashboardWidgetCardProps) {
  return (
    <Card className={cn(className)}>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-sm font-medium text-muted-foreground">{title}</CardTitle>
        <div className="flex items-center gap-2">
          {actions}
          {Icon ? <Icon className="size-4 text-muted-foreground" aria-hidden="true" /> : null}
        </div>
      </CardHeader>
      <CardContent className={cn(contentClassName)}>
        {isLoading ? (
          <div className="space-y-2">
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-5/6" />
            <Skeleton className="h-4 w-2/3" />
          </div>
        ) : isError ? (
          <ErrorState
            title="Couldn't load this"
            description="We couldn't load this widget's data. Please try again."
            onRetry={onRetry}
          />
        ) : isEmpty ? (
          <EmptyState title={emptyTitle} description={emptyDescription} />
        ) : (
          children
        )}
      </CardContent>
    </Card>
  );
}
