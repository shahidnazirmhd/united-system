import { Lock, Plus, Search, ShieldCheck } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Pagination } from "@/components/ui/pagination";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { ConfirmDialog, EmptyState, ErrorState, PageHeader, PageLoader } from "@/components/common";
import { ROUTE_PATHS } from "@/app/router/routePaths";
import { useDebouncedValue } from "@/hooks";
import { useHasPermission } from "@/lib/auth";
import { CreateUserDialog } from "@/modules/users/components/CreateUserDialog";
import { EditUserDialog } from "@/modules/users/components/EditUserDialog";
import { LinkUserToEmployeeDialog } from "@/modules/users/components/LinkUserToEmployeeDialog";
import { UserTable } from "@/modules/users/components/UserTable";
import {
  useActivateUserMutation,
  useDeactivateUserMutation,
  useRequestPasswordResetMutation,
} from "@/modules/users/hooks/useUserMutations";
import { useUsersQuery } from "@/modules/users/hooks/useUserQueries";
import type { ManagedUser, UserListFilters } from "@/modules/users/types/user.types";

const ALL_VALUE = "__all__";
const DEFAULT_FILTERS: UserListFilters = { page: 1, pageSize: 25 };

type PendingAction =
  | { type: "activate" | "deactivate" | "resetPassword"; user: ManagedUser }
  | null;

/**
 * User Management (Phase 12): List/Create/Edit/Activate/Deactivate/
 * Link-to-Employee/Reset Password.
 *
 * RBAC review round: access is gated on `identity.view_users`/
 * `identity.manage_users` — matching `LeaveDashboardPage.tsx`'s existing
 * "page renders a restricted `EmptyState` instead of the real content"
 * pattern for a caller who reaches this URL directly despite the sidebar
 * now hiding it (see `navigation.ts`). Mutating actions (New User, and
 * every row action in `UserTable`) are further gated on
 * `identity.manage_users` specifically, since `identity.view_users` alone
 * is read-only by design.
 */
export function UserListPage() {
  const navigate = useNavigate();
  const canManage = useHasPermission("identity.manage_users");
  const canViewOnly = useHasPermission("identity.view_users");
  const canView = canManage || canViewOnly;
  const canManageRolesPermission = useHasPermission("identity.manage_roles");
  const canViewRolesPermission = useHasPermission("identity.view_roles");
  const canManageRoles = canManageRolesPermission || canViewRolesPermission;
  const [filters, setFilters] = useState<UserListFilters>(DEFAULT_FILTERS);
  const [searchInput, setSearchInput] = useState("");
  const debouncedSearch = useDebouncedValue(searchInput);

  const effectiveFilters: UserListFilters = { ...filters, search: debouncedSearch || undefined };
  const { data, isLoading, isError, refetch } = useUsersQuery(effectiveFilters);

  const activateMutation = useActivateUserMutation();
  const deactivateMutation = useDeactivateUserMutation();
  const resetPasswordMutation = useRequestPasswordResetMutation();

  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [editingUser, setEditingUser] = useState<ManagedUser | undefined>(undefined);
  const [linkingUser, setLinkingUser] = useState<ManagedUser | undefined>(undefined);
  const [pendingAction, setPendingAction] = useState<PendingAction>(null);

  const handleConfirm = () => {
    if (!pendingAction) return;
    const { type, user } = pendingAction;

    if (type === "activate") {
      activateMutation.mutate(user.id, {
        onSuccess: () => {
          toast.success(`${user.email} activated.`);
          setPendingAction(null);
        },
        onError: (error) => toast.error(error.message),
      });
    } else if (type === "deactivate") {
      deactivateMutation.mutate(user.id, {
        onSuccess: () => {
          toast.success(`${user.email} deactivated.`);
          setPendingAction(null);
        },
        onError: (error) => toast.error(error.message),
      });
    } else {
      resetPasswordMutation.mutate(user.email, {
        onSuccess: () => {
          toast.success(`If ${user.email} exists, a reset link was sent.`);
          setPendingAction(null);
        },
        onError: (error) => toast.error(error.message),
      });
    }
  };

  const isConfirming =
    activateMutation.isPending || deactivateMutation.isPending || resetPasswordMutation.isPending;

  if (!canView) {
    return (
      <div>
        <PageHeader title="Users" description="Authentication accounts for HR staff, managers, and administrators." />
        <EmptyState
          icon={Lock}
          title="You don't have access to User Management"
          description="Ask an administrator for the identity.view_users permission if you believe this is a mistake."
        />
      </div>
    );
  }

  return (
    <div>
      <PageHeader
        title="Users"
        description="Authentication accounts for HR staff, managers, and administrators."
        actions={
          <>
            {canManageRoles ? (
              <Button variant="ghost" onClick={() => navigate(ROUTE_PATHS.dashboard.userRoles)}>
                <ShieldCheck className="size-4" aria-hidden="true" />
                Manage Roles
              </Button>
            ) : null}
            {canManage ? (
              <Button onClick={() => setCreateDialogOpen(true)}>
                <Plus className="size-4" aria-hidden="true" />
                New User
              </Button>
            ) : null}
          </>
        }
      />

      <div className="space-y-4">
        <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-center">
          <div className="relative w-full sm:w-64">
            <Search
              className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground"
              aria-hidden="true"
            />
            <Input
              value={searchInput}
              onChange={(event) => setSearchInput(event.target.value)}
              placeholder="Search by email…"
              className="pl-8"
              aria-label="Search users"
            />
          </div>

          <Select
            value={filters.isActive === undefined ? ALL_VALUE : String(filters.isActive)}
            onValueChange={(value) =>
              setFilters((current) => ({
                ...current,
                isActive: value === ALL_VALUE ? undefined : value === "true",
                page: 1,
              }))
            }
          >
            <SelectTrigger className="w-full sm:w-40" aria-label="Filter by status">
              <SelectValue placeholder="All statuses" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL_VALUE}>All statuses</SelectItem>
              <SelectItem value="true">Active</SelectItem>
              <SelectItem value="false">Inactive</SelectItem>
            </SelectContent>
          </Select>
        </div>

        {isLoading ? (
          <PageLoader label="Loading users…" />
        ) : isError ? (
          <ErrorState
            title="Couldn't load users"
            onRetry={() => {
              void refetch();
            }}
          />
        ) : data && data.items.length > 0 ? (
          <div className="rounded-lg border border-border">
            <UserTable
              users={data.items}
              canManage={canManage}
              onEdit={setEditingUser}
              onActivate={(user) => setPendingAction({ type: "activate", user })}
              onDeactivate={(user) => setPendingAction({ type: "deactivate", user })}
              onResetPassword={(user) => setPendingAction({ type: "resetPassword", user })}
              onLinkToEmployee={setLinkingUser}
            />
            <Pagination
              page={data.meta.page}
              totalPages={data.meta.total_pages}
              totalCount={data.meta.total_count}
              pageSize={data.meta.page_size}
              onPageChange={(page) => setFilters((current) => ({ ...current, page }))}
            />
          </div>
        ) : (
          <EmptyState
            icon={ShieldCheck}
            title="No users found"
            description={
              canManage
                ? "Try adjusting your filters, or create the first user account."
                : "Try adjusting your filters."
            }
            action={
              canManage ? (
                <Button onClick={() => setCreateDialogOpen(true)}>
                  <Plus className="size-4" aria-hidden="true" />
                  New User
                </Button>
              ) : undefined
            }
          />
        )}
      </div>

      <CreateUserDialog open={createDialogOpen} onOpenChange={setCreateDialogOpen} />
      <EditUserDialog
        open={Boolean(editingUser)}
        onOpenChange={(open) => !open && setEditingUser(undefined)}
        user={editingUser}
      />
      <LinkUserToEmployeeDialog
        open={Boolean(linkingUser)}
        onOpenChange={(open) => !open && setLinkingUser(undefined)}
        user={linkingUser}
      />
      <ConfirmDialog
        open={pendingAction !== null}
        onOpenChange={(open) => !open && setPendingAction(null)}
        title={
          pendingAction?.type === "activate"
            ? "Activate this user?"
            : pendingAction?.type === "deactivate"
              ? "Deactivate this user?"
              : "Send password reset?"
        }
        description={
          pendingAction?.type === "activate" ? (
            `${pendingAction.user.email} will regain access immediately.`
          ) : pendingAction?.type === "deactivate" ? (
            `${pendingAction.user.email}'s existing sessions will stop working on their very next request.`
          ) : pendingAction ? (
            `A password reset link will be sent to ${pendingAction.user.email} if that address is registered.`
          ) : (
            ""
          )
        }
        confirmLabel={
          pendingAction?.type === "deactivate" ? "Deactivate" : pendingAction?.type === "activate" ? "Activate" : "Send"
        }
        confirmVariant={pendingAction?.type === "deactivate" ? "destructive" : "default"}
        isConfirming={isConfirming}
        onConfirm={handleConfirm}
      />
    </div>
  );
}
