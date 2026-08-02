import { API_ENDPOINTS } from "@/lib/api/endpoints";
import { httpClient } from "@/lib/api/httpClient";
import type { ApiSuccessResponse } from "@/lib/api/types";
import type { Permission, Role, RoleFormInput } from "@/modules/users/types/role.types";

/** The exact wire shape IDENTITY_API.md documents for `RoleSerializer`. */
interface RoleWireResponse {
  id: string;
  name: string;
  description: string;
  is_system_role: boolean;
  permission_codes: string[];
}

interface PermissionWireResponse {
  id: string;
  code: string;
  description: string;
  module: string;
}

function toRole(wire: RoleWireResponse): Role {
  return {
    id: wire.id,
    name: wire.name,
    description: wire.description,
    isSystemRole: wire.is_system_role,
    permissionCodes: wire.permission_codes,
  };
}

function toPermission(wire: PermissionWireResponse): Permission {
  return { id: wire.id, code: wire.code, description: wire.description, module: wire.module };
}

/**
 * `GET /api/v1/auth/roles/` — a plain array, not `PagedResult`: unlike
 * Users/Employees/Departments, `ListRolesUseCase` returns every role
 * unpaginated (see `list_roles.py`) — an organization's role count is small
 * enough (a handful of system + custom roles) that pagination would be
 * over-engineering, matching `useAllDepartmentsQuery`'s same call on
 * Department's own list.
 */
export async function listRoles(): Promise<Role[]> {
  const response = await httpClient.get<ApiSuccessResponse<RoleWireResponse[]>>(
    `${API_ENDPOINTS.auth}/roles/`,
  );
  return response.data.data.map(toRole);
}

/** `GET /api/v1/auth/roles/{id}/` */
export async function getRoleById(roleId: string): Promise<Role> {
  const response = await httpClient.get<ApiSuccessResponse<RoleWireResponse>>(
    `${API_ENDPOINTS.auth}/roles/${roleId}/`,
  );
  return toRole(response.data.data);
}

/** `POST /api/v1/auth/roles/` */
export async function createRole(input: RoleFormInput): Promise<Role> {
  const response = await httpClient.post<ApiSuccessResponse<RoleWireResponse>>(
    `${API_ENDPOINTS.auth}/roles/`,
    { name: input.name, description: input.description, permission_codes: input.permissionCodes },
  );
  return toRole(response.data.data);
}

/**
 * `PATCH /api/v1/auth/roles/{id}/` — full-replace, matching
 * `UpdateRoleSerializer`'s contract: `permissionCodes` must be the complete
 * target set, not a diff from the role's current permissions.
 */
export async function updateRole(roleId: string, input: RoleFormInput): Promise<Role> {
  const response = await httpClient.patch<ApiSuccessResponse<RoleWireResponse>>(
    `${API_ENDPOINTS.auth}/roles/${roleId}/`,
    { name: input.name, description: input.description, permission_codes: input.permissionCodes },
  );
  return toRole(response.data.data);
}

/**
 * `DELETE /api/v1/auth/roles/{id}/`. Backend rejects with 409
 * (`cannot_delete_system_role` / `role_in_use`) if the role is a system role
 * or still assigned to any user — surfaced via `ApiError.code`, not a
 * generic message, so the UI can show the specific reason.
 */
export async function deleteRole(roleId: string): Promise<void> {
  await httpClient.delete(`${API_ENDPOINTS.auth}/roles/${roleId}/`);
}

/** `GET /api/v1/auth/permissions/` — feeds the Role form's permission picker. */
export async function listPermissions(): Promise<Permission[]> {
  const response = await httpClient.get<ApiSuccessResponse<PermissionWireResponse[]>>(
    `${API_ENDPOINTS.auth}/permissions/`,
  );
  return response.data.data.map(toPermission);
}
