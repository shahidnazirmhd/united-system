import { MoreHorizontal, Pencil, Trash2 } from "lucide-react";

import { Badge } from "@/components/ui/badge";
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
import type { Role } from "@/modules/users/types/role.types";

const MAX_PERMISSIONS_SHOWN = 3;

interface RoleTableProps {
  roles: Role[];
  /** RBAC review round: `identity.manage_roles` — without it, the Actions
   * column is omitted entirely (view-only). */
  canManage: boolean;
  onEdit: (role: Role) => void;
  onDelete: (role: Role) => void;
}

/**
 * Role Management (Role & Permission Management phase) — mirrors
 * `DepartmentTable.tsx`'s shape. Delete is always offered in the row menu
 * (never hidden for a system role) so the backend's actual rejection reason
 * — `cannot_delete_system_role` vs. `role_in_use` — surfaces as a specific
 * toast message rather than the UI silently guessing which one applies;
 * see `RolesPage.tsx`'s delete handler.
 */
export function RoleTable({ roles, canManage, onEdit, onDelete }: RoleTableProps) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Name</TableHead>
          <TableHead>Description</TableHead>
          <TableHead>Permissions</TableHead>
          <TableHead>Type</TableHead>
          {canManage ? (
            <TableHead className="w-10">
              <span className="sr-only">Actions</span>
            </TableHead>
          ) : null}
        </TableRow>
      </TableHeader>
      <TableBody>
        {roles.map((role) => {
          const shown = role.permissionCodes.slice(0, MAX_PERMISSIONS_SHOWN);
          const remaining = role.permissionCodes.length - shown.length;
          return (
            <TableRow key={role.id}>
              <TableCell>
                <div className="font-medium text-foreground">{role.name}</div>
              </TableCell>
              <TableCell className="max-w-xs truncate text-muted-foreground">
                {role.description || "—"}
              </TableCell>
              <TableCell>
                {role.permissionCodes.length === 0 ? (
                  <span className="text-sm text-muted-foreground">No permissions</span>
                ) : (
                  <div className="flex flex-wrap gap-1">
                    {shown.map((code) => (
                      <Badge key={code} variant="outline">
                        {code}
                      </Badge>
                    ))}
                    {remaining > 0 ? <Badge variant="secondary">+{remaining} more</Badge> : null}
                  </div>
                )}
              </TableCell>
              <TableCell>
                <Badge variant={role.isSystemRole ? "default" : "secondary"}>
                  {role.isSystemRole ? "System" : "Custom"}
                </Badge>
              </TableCell>
              {canManage ? (
                <TableCell>
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button variant="ghost" size="icon" aria-label={`Actions for ${role.name}`}>
                        <MoreHorizontal className="size-4" aria-hidden="true" />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      <DropdownMenuItem onClick={() => onEdit(role)}>
                        <Pencil className="mr-2 size-4" aria-hidden="true" />
                        Edit
                      </DropdownMenuItem>
                      <DropdownMenuItem onClick={() => onDelete(role)} className="text-destructive">
                        <Trash2 className="mr-2 size-4" aria-hidden="true" />
                        Delete
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </TableCell>
              ) : null}
            </TableRow>
          );
        })}
      </TableBody>
    </Table>
  );
}
