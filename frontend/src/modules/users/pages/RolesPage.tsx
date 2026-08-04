import { ArrowLeft, Lock, Plus } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { ConfirmDialog, EmptyState, ErrorState, PageHeader, PageLoader } from "@/components/common";
import { ROUTE_PATHS } from "@/app/router/routePaths";
import { useHasPermission } from "@/lib/auth";
import { RoleFormDialog } from "@/modules/users/components/RoleFormDialog";
import { RoleTable } from "@/modules/users/components/RoleTable";
import {
  useCreateRoleMutation,
  useDeleteRoleMutation,
  useUpdateRoleMutation,
} from "@/modules/users/hooks/useRoleMutations";
import { useRolesQuery } from "@/modules/users/hooks/useRoleQueries";
import type { Role } from "@/modules/users/types/role.types";
import type { RoleFormValues } from "@/modules/users/validation/roleSchema";

/**
 * Role Management (Role & Permission Management phase) — a sub-view of User
 * Management, reached only via the Users list page's header action, never
 * the sidebar — exactly the same placement rule `DepartmentsPage.tsx`
 * established for Department under Employees. Create/Edit share one dialog
 * (`RoleFormDialog`); Delete is a confirm dialog whose message is filled in
 * only after the backend's specific rejection code is known (see
 * `handleDelete` below) rather than guessed up front.
 *
 * RBAC review round: gated on `identity.view_roles`/`identity.manage_roles`,
 * same restricted-`EmptyState` pattern as `UserListPage.tsx`/
 * `LeaveDashboardPage.tsx` — Create/Edit/Delete further require
 * `identity.manage_roles` specifically.
 */
export function RolesPage() {
  const navigate = useNavigate();
  const canManage = useHasPermission("identity.manage_roles");
  const canViewOnly = useHasPermission("identity.view_roles");
  const canView = canManage || canViewOnly;
  const { data: roles, isLoading, isError, refetch } = useRolesQuery();
  const createMutation = useCreateRoleMutation();
  const updateMutation = useUpdateRoleMutation();
  const deleteMutation = useDeleteRoleMutation();

  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingRole, setEditingRole] = useState<Role | undefined>(undefined);
  const [deletingRole, setDeletingRole] = useState<Role | undefined>(undefined);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const openCreateDialog = () => {
    setEditingRole(undefined);
    setSubmitError(null);
    setDialogOpen(true);
  };

  const openEditDialog = (role: Role) => {
    setEditingRole(role);
    setSubmitError(null);
    setDialogOpen(true);
  };

  const handleSubmit = (values: RoleFormValues) => {
    setSubmitError(null);
    const input = {
      name: values.name,
      description: values.description,
      permissionCodes: values.permissionCodes,
    };

    if (editingRole) {
      updateMutation.mutate(
        { roleId: editingRole.id, input },
        {
          onSuccess: (role) => {
            toast.success(`${role.name} was updated.`);
            setDialogOpen(false);
          },
          onError: (error) => setSubmitError(error.message),
        },
      );
    } else {
      createMutation.mutate(input, {
        onSuccess: (role) => {
          toast.success(`${role.name} was created.`);
          setDialogOpen(false);
        },
        onError: (error) => setSubmitError(error.message),
      });
    }
  };

  const handleDelete = () => {
    if (!deletingRole) return;
    deleteMutation.mutate(deletingRole.id, {
      onSuccess: () => {
        toast.success(`${deletingRole.name} was deleted.`);
        setDeletingRole(undefined);
      },
      onError: (error) => {
        // `cannot_delete_system_role` / `role_in_use` (see roleApi.ts's
        // deleteRole docstring) are specific enough to show as-is; anything
        // else falls back to the generic message.
        toast.error(error.message);
        setDeletingRole(undefined);
      },
    });
  };

  if (!canView) {
    return (
      <div>
        <PageHeader
          title="Roles"
          description="Roles and their permissions, assignable to any user."
          actions={
            <Button variant="ghost" onClick={() => navigate(ROUTE_PATHS.dashboard.users)}>
              <ArrowLeft className="size-4" aria-hidden="true" />
              Back to Users
            </Button>
          }
        />
        <EmptyState
          icon={Lock}
          title="You don't have access to Role Management"
          description="Ask an administrator for the identity.view_roles permission if you believe this is a mistake."
        />
      </div>
    );
  }

  return (
    <div>
      <PageHeader
        title="Roles"
        description="Roles and their permissions, assignable to any user."
        actions={
          <>
            <Button variant="ghost" onClick={() => navigate(ROUTE_PATHS.dashboard.users)}>
              <ArrowLeft className="size-4" aria-hidden="true" />
              Back to Users
            </Button>
            {canManage ? (
              <Button onClick={openCreateDialog}>
                <Plus className="size-4" aria-hidden="true" />
                New Role
              </Button>
            ) : null}
          </>
        }
      />

      {isLoading ? (
        <PageLoader label="Loading roles…" />
      ) : isError ? (
        <ErrorState
          title="Couldn't load roles"
          onRetry={() => {
            void refetch();
          }}
        />
      ) : roles && roles.length > 0 ? (
        <div className="rounded-lg border border-border">
          <RoleTable
            roles={roles}
            canManage={canManage}
            onEdit={openEditDialog}
            onDelete={setDeletingRole}
          />
        </div>
      ) : (
        <EmptyState
          title="No roles yet"
          description={
            canManage
              ? "Create the first custom role to start assigning it to users."
              : "No custom roles have been created yet."
          }
          action={
            canManage ? (
              <Button onClick={openCreateDialog}>
                <Plus className="size-4" aria-hidden="true" />
                New Role
              </Button>
            ) : undefined
          }
        />
      )}

      <RoleFormDialog
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        role={editingRole}
        onSubmit={handleSubmit}
        isSubmitting={createMutation.isPending || updateMutation.isPending}
        submitError={submitError}
      />

      <ConfirmDialog
        open={Boolean(deletingRole)}
        onOpenChange={(open) => !open && setDeletingRole(undefined)}
        title="Delete this role?"
        description={
          deletingRole
            ? `${deletingRole.name} will be permanently deleted. This only succeeds if it isn't currently assigned to any user.`
            : ""
        }
        confirmLabel="Delete"
        confirmVariant="destructive"
        isConfirming={deleteMutation.isPending}
        onConfirm={handleDelete}
      />
    </div>
  );
}
