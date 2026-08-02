import { useQuery, type UseQueryResult } from "@tanstack/react-query";

import type { ApiError } from "@/lib/api/types";
import { getRoleById, listPermissions, listRoles } from "@/modules/users/api/roleApi";
import type { Permission, Role } from "@/modules/users/types/role.types";

export function useRolesQuery(): UseQueryResult<Role[], ApiError> {
  return useQuery({
    queryKey: ["roles", "list"],
    queryFn: listRoles,
  });
}

export function useRoleQuery(roleId: string | undefined): UseQueryResult<Role, ApiError> {
  return useQuery({
    queryKey: ["roles", "detail", roleId],
    queryFn: () => getRoleById(roleId as string),
    enabled: Boolean(roleId),
  });
}

/**
 * Feeds the Role create/edit form's permission checklist, and the Create/Edit
 * User dialogs' role checklist relies on `useRolesQuery` above for the same
 * reason — a small, rarely-changing catalogue, safe to keep at a longer
 * `staleTime` than most list queries in this app.
 */
export function usePermissionsQuery(): UseQueryResult<Permission[], ApiError> {
  return useQuery({
    queryKey: ["permissions", "list"],
    queryFn: listPermissions,
    staleTime: 60_000,
  });
}
