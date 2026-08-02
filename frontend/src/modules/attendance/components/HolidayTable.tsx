import { Pencil } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import type { Holiday } from "@/modules/attendance/types/holiday.types";

interface HolidayTableProps {
  holidays: Holiday[];
  onEdit: (holiday: Holiday) => void;
}

export function HolidayTable({ holidays, onEdit }: HolidayTableProps) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Name</TableHead>
          <TableHead>Date</TableHead>
          <TableHead>Description</TableHead>
          <TableHead>Status</TableHead>
          <TableHead className="w-10">
            <span className="sr-only">Actions</span>
          </TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {holidays.map((holiday) => (
          <TableRow key={holiday.id}>
            <TableCell className="font-medium text-foreground">{holiday.name}</TableCell>
            <TableCell className="text-muted-foreground">{holiday.holidayDate}</TableCell>
            <TableCell className="text-muted-foreground">{holiday.description || "—"}</TableCell>
            <TableCell>
              <Badge variant={holiday.isActive ? "success" : "secondary"}>
                {holiday.isActive ? "Active" : "Inactive"}
              </Badge>
            </TableCell>
            <TableCell>
              <Button
                variant="ghost"
                size="icon"
                aria-label={`Edit ${holiday.name}`}
                onClick={() => onEdit(holiday)}
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
