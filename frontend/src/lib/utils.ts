import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

/**
 * Merges Tailwind class lists, resolving conflicting utilities (e.g.
 * `"px-2"` + `"px-4"` → `"px-4"`) the way a human would expect, rather than
 * both ending up in the DOM and letting CSS source order decide. This is
 * the shadcn/ui standard helper — kept at this exact path (`@/lib/utils`)
 * so `npx shadcn@latest add <component>` continues to work unmodified for
 * any component added in a later phase (see components.json's `aliases.utils`).
 */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}
