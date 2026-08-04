import { KeyRound, Link2, MoreHorizontal, Pencil } from "lucide-react";

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
import type { ManagedUser } from "@/modules/users/types/user.types";

interface UserTableProps {
  users: ManagedUser[];
  /** RBAC review round: `identity.manage_users` — without it, the whole
   * Actions column is omitted rather than shown-but-disabled, since every
   * action here (edit, link, reset, activate/deactivate) is a mutation a
   * view-only caller has no valid use for. */
  canManage: boolean;
  onEdit: (user: ManagedUser) => void;
  onActivate: (user: ManagedUser) => void;
  onDeactivate: (user: ManagedUser) => void;
  onResetPassword: (user: ManagedUser) => void;
  onLinkToEmployee: (user: ManagedUser) => void;
}

export function UserTable({
  users,
  canManage,
  onEdit,
  onActivate,
  onDeactivate,
  onResetPassword,
  onLinkToEmployee,
}: UserTableProps) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Email</TableHead>
          <TableHead>Roles</TableHead>
          <TableHead>Linked employee</TableHead>
          <TableHead>Status</TableHead>
          {canManage ? (
            <TableHead className="w-10">
              <span className="sr-only">Actions</span>
            </TableHead>
          ) : null}
        </TableRow>
      </TableHeader>
      <TableBody>
        {users.map((user) => (
          <TableRow key={user.id}>
            <TableCell>
              <div className="font-medium text-foreground">{user.email}</div>
            </TableCell>
            <TableCell className="text-muted-foreground">
              {user.roles.length > 0 ? user.roles.map((role) => role.name).join(", ") : "—"}
            </TableCell>
            <TableCell className="text-muted-foreground">
              {user.employeeId ? "Linked" : "Not linked"}
            </TableCell>
            <TableCell>
              <Badge variant={user.isActive ? "success" : "secondary"}>
                {user.isActive ? "Active" : "Inactive"}
              </Badge>
            </TableCell>
            {canManage ? (
              <TableCell>
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button variant="ghost" size="icon" aria-label={`Actions for ${user.email}`}>
                      <MoreHorizontal className="size-4" aria-hidden="true" />
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end">
                    <DropdownMenuItem onClick={() => onEdit(user)}>
                      <Pencil className="mr-2 size-4" aria-hidden="true" />
                      Edit
                    </DropdownMenuItem>
                    {user.employeeId ? null : (
                      <DropdownMenuItem onClick={() => onLinkToEmployee(user)}>
                        <Link2 className="mr-2 size-4" aria-hidden="true" />
                        Link to employee
                      </DropdownMenuItem>
                    )}
                    <DropdownMenuItem onClick={() => onResetPassword(user)}>
                      <KeyRound className="mr-2 size-4" aria-hidden="true" />
                      Send password reset
                    </DropdownMenuItem>
                    {user.isActive ? (
                      <DropdownMenuItem onClick={() => onDeactivate(user)}>
                        Deactivate
                      </DropdownMenuItem>
                    ) : (
                      <DropdownMenuItem onClick={() => onActivate(user)}>Activate</DropdownMenuItem>
                    )}
                  </DropdownMenuContent>
                </DropdownMenu>
              </TableCell>
            ) : null}
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
