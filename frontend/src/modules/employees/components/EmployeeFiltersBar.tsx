import { Search, X } from "lucide-react";
import { useEffect, useState } from "react";

import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import { useDebouncedValue } from "@/hooks";
import { useAllDepartmentsQuery } from "@/modules/employees/hooks/useDepartmentQueries";
import {
  EMPLOYEE_STATUS_OPTIONS,
  EMPLOYMENT_TYPE_OPTIONS,
  type EmployeeListFilters,
} from "@/modules/employees/types/employee.types";

interface EmployeeFiltersBarProps {
  filters: EmployeeListFilters;
  onFiltersChange: (filters: EmployeeListFilters) => void;
}

const ALL_VALUE = "__all__";

/**
 * Search box + three exact-match filters (department, employment status,
 * employment type) mirroring EMPLOYEE_API.md's `GET /api/v1/employees/`
 * query parameters exactly — one Select maps to one filter, nothing here
 * invents a filter the backend doesn't support. Search is debounced
 * (`useDebouncedValue`) before it reaches the parent's `filters` state, so
 * typing doesn't fire a request per keystroke.
 */
export function EmployeeFiltersBar({ filters, onFiltersChange }: EmployeeFiltersBarProps) {
  const [searchInput, setSearchInput] = useState(filters.search ?? "");
  const debouncedSearch = useDebouncedValue(searchInput);
  const { data: departmentsPage } = useAllDepartmentsQuery();

  useEffect(() => {
    if (debouncedSearch !== (filters.search ?? "")) {
      onFiltersChange({ ...filters, search: debouncedSearch || undefined, page: 1 });
    }
    // Only re-run when the debounced search text itself changes — including
    // `filters`/`onFiltersChange` here would re-fire every time the parent's
    // filters object identity changes (e.g. a different Select), which is
    // exactly the loop this effect must not create.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [debouncedSearch]);

  const hasActiveFilters = Boolean(
    filters.search || filters.departmentId || filters.employmentStatus || filters.employmentType,
  );

  return (
    <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-center">
      <div className="relative w-full sm:w-64">
        <Search
          className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground"
          aria-hidden="true"
        />
        <Input
          value={searchInput}
          onChange={(event) => setSearchInput(event.target.value)}
          placeholder="Search name, code, or email…"
          className="pl-8"
          aria-label="Search employees"
        />
      </div>

      <Select
        value={filters.departmentId ?? ALL_VALUE}
        onValueChange={(value) =>
          onFiltersChange({
            ...filters,
            departmentId: value === ALL_VALUE ? undefined : value,
            page: 1,
          })
        }
      >
        <SelectTrigger className="w-full sm:w-48" aria-label="Filter by department">
          <SelectValue placeholder="All departments" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value={ALL_VALUE}>All departments</SelectItem>
          {(departmentsPage?.items ?? []).map((department) => (
            <SelectItem key={department.id} value={department.id}>
              {department.name}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>

      <Select
        value={filters.employmentStatus ?? ALL_VALUE}
        onValueChange={(value) =>
          onFiltersChange({
            ...filters,
            employmentStatus:
              value === ALL_VALUE ? undefined : (value as EmployeeListFilters["employmentStatus"]),
            page: 1,
          })
        }
      >
        <SelectTrigger className="w-full sm:w-40" aria-label="Filter by status">
          <SelectValue placeholder="All statuses" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value={ALL_VALUE}>All statuses</SelectItem>
          {EMPLOYEE_STATUS_OPTIONS.map((option) => (
            <SelectItem key={option.value} value={option.value}>
              {option.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>

      <Select
        value={filters.employmentType ?? ALL_VALUE}
        onValueChange={(value) =>
          onFiltersChange({
            ...filters,
            employmentType:
              value === ALL_VALUE ? undefined : (value as EmployeeListFilters["employmentType"]),
            page: 1,
          })
        }
      >
        <SelectTrigger className="w-full sm:w-40" aria-label="Filter by employment type">
          <SelectValue placeholder="All types" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value={ALL_VALUE}>All types</SelectItem>
          {EMPLOYMENT_TYPE_OPTIONS.map((option) => (
            <SelectItem key={option.value} value={option.value}>
              {option.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>

      {hasActiveFilters ? (
        <Button
          variant="ghost"
          size="sm"
          onClick={() => {
            setSearchInput("");
            onFiltersChange({ page: 1, pageSize: filters.pageSize });
          }}
        >
          <X className="size-4" aria-hidden="true" />
          Clear filters
        </Button>
      ) : null}
    </div>
  );
}
