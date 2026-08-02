import { Loader2, Search, X } from "lucide-react";
import { useState } from "react";

import { Input } from "@/components/ui/input";
import { useDebouncedValue } from "@/hooks";
import { useActiveEmployeeSearchQuery } from "@/modules/leave/hooks/useLeaveQueries";
import type { LeaveEmployeeOption } from "@/modules/leave/types/leave.types";

interface LeaveEmployeePickerFieldProps {
  selected: LeaveEmployeeOption | null;
  onSelect: (employee: LeaveEmployeeOption | null) => void;
}

/**
 * Search-as-you-type employee picker for "Apply Leave for Employee" and
 * "Adjust/Open Leave Balance" (Phase 13, HR/Admin only) — same UX shape as
 * `modules/users/components/EmployeePickerField.tsx`, but this module's own
 * copy against its own narrower fetch (see api/leaveEmployeePicker.ts's
 * docstring for why: no "already linked to a user" concept applies here,
 * every active employee is a valid pick).
 */
export function LeaveEmployeePickerField({ selected, onSelect }: LeaveEmployeePickerFieldProps) {
  const [search, setSearch] = useState("");
  const debouncedSearch = useDebouncedValue(search);
  const { data: employees, isLoading } = useActiveEmployeeSearchQuery(debouncedSearch);

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
                className="flex w-full flex-col items-start gap-0.5 border-b border-border px-3 py-2 text-left text-sm last:border-b-0 hover:bg-accent"
              >
                <span className="font-medium text-foreground">{employee.fullName}</span>
                <span className="text-xs text-muted-foreground">{employee.employeeCode}</span>
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
