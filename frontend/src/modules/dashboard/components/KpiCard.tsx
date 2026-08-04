import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

interface KpiCardProps {
  label: string;
  value: ReactNode;
  icon: LucideIcon;
  helpText?: string;
  isLoading?: boolean;
  className?: string;
}

/**
 * The one generic building block every KPI number on the Dashboard renders
 * through — Employee Statistics, Leave Statistics, and any future module's
 * counts all use this same component with different `label`/`value`/`icon`
 * props, rather than each hand-rolling its own card markup. This is the
 * concrete mechanism behind "new dashboard KPIs can be added easily": a
 * future widget is a one-line `<KpiCard .../>` addition to a grid, not a
 * new component.
 */
export function KpiCard({
  label,
  value,
  icon: Icon,
  helpText,
  isLoading = false,
  className,
}: KpiCardProps) {
  return (
    <Card className={cn(className)}>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-sm font-medium text-muted-foreground">{label}</CardTitle>
        <Icon className="size-4 text-muted-foreground" aria-hidden="true" />
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <Skeleton className="h-8 w-16" />
        ) : (
          <div className="text-2xl font-semibold text-foreground">{value}</div>
        )}
        {helpText && !isLoading ? (
          <p className="mt-1 text-xs text-muted-foreground">{helpText}</p>
        ) : null}
      </CardContent>
    </Card>
  );
}
