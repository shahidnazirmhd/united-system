import { Pencil } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { Department } from "@/modules/employees/types/department.types";

interface DepartmentTableProps {
  departments: Department[];
  onEdit: (department: Department) => void;
}

export function DepartmentTable({ departments, onEdit }: DepartmentTableProps) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Name</TableHead>
          <TableHead>Code</TableHead>
          <TableHead>Status</TableHead>
          <TableHead className="w-10">
            <span className="sr-only">Actions</span>
          </TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {departments.map((department) => (
          <TableRow key={department.id}>
            <TableCell className="font-medium text-foreground">{department.name}</TableCell>
            <TableCell className="text-muted-foreground">{department.code}</TableCell>
            <TableCell>
              <Badge variant={department.isActive ? "success" : "secondary"}>
                {department.isActive ? "Active" : "Inactive"}
              </Badge>
            </TableCell>
            <TableCell>
              <Button
                variant="ghost"
                size="icon"
                aria-label={`Edit ${department.name}`}
                onClick={() => onEdit(department)}
              >
                <Pencil className="size-4" aria-hidden="true" />
              </Button>
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
