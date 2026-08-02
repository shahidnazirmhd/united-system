import { Loader2, Search, X } from "lucide-react";
import { useState } from "react";

import { Input } from "@/components/ui/input";
import { useDebouncedValue } from "@/hooks";
import { useLinkableEmployeesQuery } from "@/modules/users/hooks/useUserQueries";
import type { LinkableEmployee } from "@/modules/users/api/userApi";
import { cn } from "@/lib/utils";

interface EmployeePickerFieldProps {
  selected: LinkableEmployee | null;
  onSelect: (employee: LinkableEmployee | null) => void;
}

/**
 * The inline "link to an employee" search picker embedded directly in
 * `CreateUserDialog`/`EditUserDialog` (Role & Permission Management phase's
 * "allow linking an existing Employee (optional)" requirement) — same
 * search-as-you-type UX and `GET /api/v1/employees/` query
 * `LinkUserToEmployeeDialog` already uses, just rendered as an inline field
 * instead of its own dialog. That standalone dialog (reached from the Users
 * table's row menu) is left untouched rather than refactored to share this
 * component — it already works and is already verified; this is a second,
 * separate implementation of the same small picker UI, an acceptable
 * duplication against the risk of regressing a tested flow.
 *
 * Only ever rendered for a user with no existing link (`EditUserDialog`
 * hides it once `user.employeeId` is set) — there is no unlink endpoint,
 * so once linked, this field has nothing further to offer.
 */
export function EmployeePickerField({ selected, onSelect }: EmployeePickerFieldProps) {
  const [search, setSearch] = useState("");
  const debouncedSearch = useDebouncedValue(search);
  const { data: employees, isLoading } = useLinkableEmployeesQuery(debouncedSearch);

  if (selected) {
    return (
      <div className="flex items-center justify-between rounded-md border border-border px-3 py-2 text-sm">
        <div>
          <div className="font-medium text-foreground">{selected.fullName}</div>
          <div className="text-xs text-muted-foreground">{selected.employeeCode}</div>
        </div>
        <button
          type="button"
          onClick={() => onSelect(null)}
          className="rounded p-1 text-muted-foreground hover:bg-accent hover:text-foreground"
          aria-label="Clear selected employee"
        >
          <X className="size-4" aria-hidden="true" />
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <div className="relative">
        <Search
          className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground"
          aria-hidden="true"
        />
        <Input
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          placeholder="Search by name, code, or email…"
          className="pl-8"
          aria-label="Search employees"
        />
      </div>

      {search.trim() ? (
        <div className="max-h-40 overflow-y-auto rounded-md border border-border">
          {isLoading ? (
            <div className="flex items-center justify-center gap-2 p-3 text-sm text-muted-foreground">
              <Loader2 className="size-4 animate-spin" aria-hidden="true" />
              Searching…
            </div>
          ) : employees && employees.length > 0 ? (
            employees.map((employee) => (
              <button
                key={employee.id}
                type="button"
                onClick={() => onSelect(employee)}
                disabled={Boolean(employee.userId)}
                className={cn(
                  "flex w-full flex-col items-start gap-0.5 border-b border-border px-3 py-2 text-left text-sm last:border-b-0 hover:bg-accent disabled:cursor-not-allowed disabled:opacity-50",
                )}
              >
                <span className="font-medium text-foreground">{employee.fullName}</span>
                <span className="text-xs text-muted-foreground">
                  {employee.employeeCode}
                  {employee.userId ? " · already linked to a different user" : ""}
                </span>
              </button>
            ))
          ) : (
            <div className="p-3 text-center text-sm text-muted-foreground">No employees found.</div>
          )}
        </div>
      ) : null}
    </div>
  );
}
