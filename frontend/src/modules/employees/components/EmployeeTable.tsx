import { MoreHorizontal } from "lucide-react";
import { useNavigate } from "react-router-dom";

import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { buildEmployeeDetailPath, buildEmployeeEditPath } from "@/app/router/routePaths";
import { CurrentStatusBadge } from "@/modules/employees/components/CurrentStatusBadge";
import { EmployeeStatusBadge } from "@/modules/employees/components/EmployeeStatusBadge";
import type { Employee } from "@/modules/employees/types/employee.types";

interface EmployeeTableProps {
  employees: Employee[];
  /** RBAC review round: `employees.manage_employees` — Edit/Activate/
   * Deactivate are hidden without it; "View details" always stays since it
   * needs only `employees.view_employees`, already required to reach this
   * table at all (see `EmployeeListPage.tsx`). */
  canManage: boolean;
  onActivate: (employee: Employee) => void;
  onDeactivate: (employee: Employee) => void;
}

export function EmployeeTable({
  employees,
  canManage,
  onActivate,
  onDeactivate,
}: EmployeeTableProps) {
  const navigate = useNavigate();

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Employee</TableHead>
          <TableHead>Code</TableHead>
          <TableHead>Job Title</TableHead>
          <TableHead>Department</TableHead>
          <TableHead>Type</TableHead>
          <TableHead>Status</TableHead>
          {/* Round 15 item 8 — the day-to-day working status, distinct
              from the system-access "Status" column above. */}
          <TableHead>Current Status</TableHead>
          <TableHead className="w-10">
            <span className="sr-only">Actions</span>
          </TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {employees.map((employee) => (
          <TableRow
            key={employee.id}
            className="cursor-pointer"
            onClick={() => navigate(buildEmployeeDetailPath(employee.id))}
          >
            <TableCell>
              <div className="font-medium text-foreground">{employee.fullName}</div>
              <div className="text-xs text-muted-foreground">{employee.workEmail}</div>
            </TableCell>
            <TableCell className="text-muted-foreground">{employee.employeeCode}</TableCell>
            <TableCell>{employee.jobTitle}</TableCell>
            <TableCell className="text-muted-foreground">
              {employee.departmentName ?? "—"}
            </TableCell>
            <TableCell className="text-muted-foreground">
              {employee.employmentType.replace("_", " ")}
            </TableCell>
            <TableCell>
              <EmployeeStatusBadge status={employee.status} />
            </TableCell>
            <TableCell>
              <CurrentStatusBadge status={employee.currentStatus} />
            </TableCell>
            <TableCell onClick={(event) => event.stopPropagation()}>
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button
                    variant="ghost"
                    size="icon"
                    aria-label={`Actions for ${employee.fullName}`}
                  >
                    <MoreHorizontal className="size-4" aria-hidden="true" />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end">
                  <DropdownMenuItem onClick={() => navigate(buildEmployeeDetailPath(employee.id))}>
                    View details
                  </DropdownMenuItem>
                  {canManage ? (
                    <DropdownMenuItem onClick={() => navigate(buildEmployeeEditPath(employee.id))}>
                      Edit
                    </DropdownMenuItem>
                  ) : null}
                  {!canManage || employee.status === "terminated" ? null : employee.status ===
                    "active" ? (
                    <DropdownMenuItem onClick={() => onDeactivate(employee)}>
                      Deactivate
                    </DropdownMenuItem>
                  ) : (
                    <DropdownMenuItem onClick={() => onActivate(employee)}>
                      Activate
                    </DropdownMenuItem>
                  )}
                </DropdownMenuContent>
              </DropdownMenu>
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
