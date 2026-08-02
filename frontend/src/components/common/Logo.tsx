import { Building2 } from "lucide-react";

import { cn } from "@/lib/utils";
import { env } from "@/config/env";

interface LogoProps {
  className?: string;
  iconOnly?: boolean;
}

/**
 * Single source of the application's brand mark. Every layout renders this
 * component rather than hardcoding the app name/icon inline, so a rebrand
 * is a one-file change.
 */
export function Logo({ className, iconOnly = false }: LogoProps) {
  return (
    <div className={cn("flex items-center gap-2 font-semibold text-foreground", className)}>
      <span className="flex size-8 shrink-0 items-center justify-center rounded-md bg-primary text-primary-foreground">
        <Building2 className="size-4" aria-hidden="true" />
      </span>
      {iconOnly ? null : <span className="text-base tracking-tight">{env.appName}</span>}
    </div>
  );
}
