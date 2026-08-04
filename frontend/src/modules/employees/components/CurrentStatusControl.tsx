import { Loader2 } from "lucide-react";
import { toast } from "sonner";

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { CurrentStatusBadge } from "@/modules/employees/components/CurrentStatusBadge";
import { useUpdateEmployeeCurrentStatusMutation } from "@/modules/employees/hooks/useEmployeeMutations";
import {
  MANUAL_CURRENT_STATUS_OPTIONS,
  type Employee,
} from "@/modules/employees/types/employee.types";

interface CurrentStatusControlProps {
  employee: Employee;
  canManage: boolean;
}

const AUTO_MANAGED_STATUSES = new Set(["sick_leave", "annual_leave"]);
const TERMINAL_STATUSES = new Set(["terminated", "resigned"]);

/**
 * Round 14 item 8 — HR-facing editor for Employee.current_status. Mirrors
 * the backend's own transition guard so the control never even offers an
 * action the API would reject: Sick Leave/Annual Leave are system-managed
 * (Leave module owns them), and Terminated/Resigned are terminal — both
 * cases render as a read-only badge with an explanatory note instead of a
 * dropdown.
 */
export function CurrentStatusControl({ employee, canManage }: CurrentStatusControlProps) {
  const updateMutation = useUpdateEmployeeCurrentStatusMutation();

  if (
    !canManage ||
    AUTO_MANAGED_STATUSES.has(employee.currentStatus) ||
    TERMINAL_STATUSES.has(employee.currentStatus)
  ) {
    return (
      <div className="flex items-center gap-2">
        <CurrentStatusBadge status={employee.currentStatus} />
        {AUTO_MANAGED_STATUSES.has(employee.currentStatus) ? (
          <span className="text-xs text-muted-foreground">Managed automatically by Leave</span>
        ) : null}
      </div>
    );
  }

  return (
    <div className="flex items-center gap-2">
      <Select
        value={employee.currentStatus}
        disabled={updateMutation.isPending}
        onValueChange={(value) => {
          updateMutation.mutate(
            { employeeId: employee.id, currentStatus: value as Employee["currentStatus"] },
            {
              onSuccess: () => toast.success("Current status updated."),
              onError: (error) => toast.error(error.message),
            },
          );
        }}
      >
        <SelectTrigger className="w-40">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {MANUAL_CURRENT_STATUS_OPTIONS.map((option) => (
            <SelectItem key={option.value} value={option.value}>
              {option.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      {updateMutation.isPending ? (
        <Loader2 className="size-4 animate-spin text-muted-foreground" aria-hidden="true" />
      ) : null}
    </div>
  );
}
