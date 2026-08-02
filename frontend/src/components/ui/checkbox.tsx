import { forwardRef, type InputHTMLAttributes } from "react";

import { cn } from "@/lib/utils";

/**
 * A plain native `<input type="checkbox">`, styled — not a Radix primitive.
 * Every other new control this UI kit has added (`select.tsx`, `dialog.tsx`,
 * `table.tsx`) wraps a Radix primitive because those need real behavior
 * (portals, focus trapping, positioning) a native element can't give you. A
 * checkbox needs none of that: `checked`/`onChange` on a native input is
 * already fully accessible and keyboard-operable. Matches this codebase's
 * own precedent of not reaching for a new dependency until the plain HTML
 * element genuinely can't do the job — see `useAllEmployeesQuery`'s
 * docstring ("no new heavy dependency for this phase's scope") for the same
 * reasoning applied to a combobox instead of a checkbox.
 */
export const Checkbox = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(
  ({ className, ...props }, ref) => (
    <input
      type="checkbox"
      ref={ref}
      className={cn(
        "size-4 shrink-0 cursor-pointer rounded-sm border border-input accent-primary disabled:cursor-not-allowed disabled:opacity-50",
        className,
      )}
      {...props}
    />
  ),
);
Checkbox.displayName = "Checkbox";
