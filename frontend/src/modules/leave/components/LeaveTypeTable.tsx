import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import type { LeaveType } from "@/modules/leave/types/leave.types";

interface LeaveTypeTableProps {
  leaveTypes: LeaveType[];
  onEdit: (leaveType: LeaveType) => void;
}

export function LeaveTypeTable({ leaveTypes, onEdit }: LeaveTypeTableProps) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Name</TableHead>
          <TableHead>Code</TableHead>
          <TableHead>Default annual days</TableHead>
          <TableHead>Paid</TableHead>
          <TableHead>Requires approval</TableHead>
          <TableHead>Status</TableHead>
          <TableHead className="text-right">Actions</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {leaveTypes.map((leaveType) => (
          <TableRow key={leaveType.id}>
            <TableCell className="font-medium text-foreground">{leaveType.name}</TableCell>
            <TableCell>{leaveType.code}</TableCell>
            <TableCell>{leaveType.defaultAnnualDays}</TableCell>
            <TableCell>{leaveType.isPaid ? "Yes" : "No"}</TableCell>
            <TableCell>{leaveType.requiresApproval ? "Yes" : "No"}</TableCell>
            <TableCell>
              <Badge variant={leaveType.isActive ? "success" : "secondary"}>
                {leaveType.isActive ? "Active" : "Inactive"}
              </Badge>
            </TableCell>
            <TableCell className="text-right">
              <Button variant="ghost" size="sm" onClick={() => onEdit(leaveType)}>
                Edit
              </Button>
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
