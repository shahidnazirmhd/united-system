import { Loader2, Search, X } from "lucide-react";
import { useState } from "react";

import { Input } from "@/components/ui/input";
import { useDebouncedValue } from "@/hooks";
import { useEmployeeSearchQuery } from "@/modules/employees/hooks/useEmployeeQueries";

export interface ManagerOption {
  id: string;
  fullName: string;
  employeeCode: string | null;
}

interface ManagerPickerFieldProps {
  selected: ManagerOption | null;
  onSelect: (employee: ManagerOption | null) => void;
  excludeEmployeeId?: string;
}

/**
 * Search-as-you-type Manager picker for the Employee form (Phase 13 review
 * requirement #4) — replaces the old `<Select>` fed by `useAllEmployeesQuery`
 * (capped at page_size 100), which doesn't scale to a real headcount. Same
 * UX shape as `modules/leave/components/LeaveEmployeePickerField.tsx`, but
 * built entirely against this module's own `Employee` type and
 * `useEmployeeSearchQuery` — the Manager field already lives inside
 * `modules/employees`, so there's no cross-module concern here, unlike the
 * Leave module's picker.
 */
export function ManagerPickerField({
  selected,
  onSelect,
  excludeEmployeeId,
}: ManagerPickerFieldProps) {
  const [search, setSearch] = useState("");
  const debouncedSearch = useDebouncedValue(search);
  const { data: results, isLoading } = useEmployeeSearchQuery(debouncedSearch);

  const options = (results?.items ?? []).filter((employee) => employee.id !== excludeEmployeeId);

  if (selected) {
    return (
      <div className="flex items-center justify-between rounded-md border border-border px-3 py-2 text-sm">
        <div>
          <div className="font-medium text-foreground">{selected.fullName}</div>
          {selected.employeeCode ? (
            <div className="text-xs text-muted-foreground">{selected.employeeCode}</div>
          ) : null}
        </div>
        <button
          type="button"
          onClick={() => onSelect(null)}
          className="rounded p-1 text-muted-foreground hover:bg-accent hover:text-foreground"
          aria-label="Clear selected manager"
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
          placeholder="Search by name or employee code…"
          className="pl-8"
          aria-label="Search employees for manager"
        />
      </div>

      {search.trim() ? (
        <div className="max-h-40 overflow-y-auto rounded-md border border-border">
          {isLoading ? (
            <div className="flex items-center justify-center gap-2 p-3 text-sm text-muted-foreground">
              <Loader2 className="size-4 animate-spin" aria-hidden="true" />
              Searching…
            </div>
          ) : options.length > 0 ? (
            options.map((employee) => (
              <button
                key={employee.id}
                type="button"
                onClick={() =>
                  onSelect({
                    id: employee.id,
                    fullName: employee.fullName,
                    employeeCode: employee.employeeCode,
                  })
                }
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
