import { API_ENDPOINTS } from "@/lib/api/endpoints";
import { httpClient } from "@/lib/api/httpClient";
import type { ApiSuccessResponse, PagedResult } from "@/lib/api/types";
import type {
  CreateUserInput,
  ManagedUser,
  UpdateUserInput,
  UserListFilters,
} from "@/modules/users/types/user.types";

/** The exact wire shape IDENTITY_API.md documents for `UserSummarySerializer`. */
interface UserWireResponse {
  id: string;
  email: string;
  is_active: boolean;
  employee_id: string | null;
  roles: { id: string; name: string }[];
  permission_codes: string[];
}

function toManagedUser(wire: UserWireResponse): ManagedUser {
  return {
    id: wire.id,
    email: wire.email,
    isActive: wire.is_active,
    employeeId: wire.employee_id,
    roles: wire.roles,
    permissionCodes: wire.permission_codes,
  };
}

/** `GET /api/v1/auth/users/` (Phase 12) */
export async function listUsers(filters: UserListFilters): Promise<PagedResult<ManagedUser>> {
  const response = await httpClient.get<ApiSuccessResponse<UserWireResponse[]>>(
    `${API_ENDPOINTS.auth}/users/`,
    {
      params: {
        is_active: filters.isActive,
        search: filters.search || undefined,
        ordering: filters.ordering,
        page: filters.page,
        page_size: filters.pageSize,
      },
    },
  );
  return {
    items: response.data.data.map(toManagedUser),
    meta: response.data.meta!,
  };
}

/** `GET /api/v1/auth/users/{id}/` (Phase 12) */
export async function getUserById(userId: string): Promise<ManagedUser> {
  const response = await httpClient.get<ApiSuccessResponse<UserWireResponse>>(
    `${API_ENDPOINTS.auth}/users/${userId}/`,
  );
  return toManagedUser(response.data.data);
}

/** `POST /api/v1/auth/users/` */
export async function createUser(input: CreateUserInput): Promise<ManagedUser> {
  const response = await httpClient.post<ApiSuccessResponse<UserWireResponse>>(
    `${API_ENDPOINTS.auth}/users/`,
    { email: input.email, password: input.password },
  );
  return toManagedUser(response.data.data);
}

/** `PATCH /api/v1/auth/users/{id}/` (Phase 12) */
export async function updateUser(userId: string, input: UpdateUserInput): Promise<ManagedUser> {
  const response = await httpClient.patch<ApiSuccessResponse<UserWireResponse>>(
    `${API_ENDPOINTS.auth}/users/${userId}/`,
    { email: input.email },
  );
  return toManagedUser(response.data.data);
}

/** `POST /api/v1/auth/users/{id}/activate/` (Phase 12) */
export async function activateUser(userId: string): Promise<ManagedUser> {
  const response = await httpClient.post<ApiSuccessResponse<UserWireResponse>>(
    `${API_ENDPOINTS.auth}/users/${userId}/activate/`,
  );
  return toManagedUser(response.data.data);
}

/** `POST /api/v1/auth/users/{id}/deactivate/` (Phase 12) */
export async function deactivateUser(userId: string): Promise<ManagedUser> {
  const response = await httpClient.post<ApiSuccessResponse<UserWireResponse>>(
    `${API_ENDPOINTS.auth}/users/${userId}/deactivate/`,
  );
  return toManagedUser(response.data.data);
}

/**
 * "Reset Password" (Phase 12) has no dedicated admin endpoint — per
 * IDENTITY_API.md's note, the admin UI calls the same public
 * `POST /auth/password-reset/request/` any user would call for themselves.
 * No `Authorization` header is required, but sending one is harmless (the
 * endpoint is `AllowAny`) — going through the shared `httpClient` anyway
 * keeps this call consistent with every other request in the app.
 */
export async function requestPasswordResetForUser(email: string): Promise<void> {
  await httpClient.post(`${API_ENDPOINTS.auth}/password-reset/request/`, { email });
}

// --- Link User to Employee (Phase 12) ---------------------------------
// Lives here, not in modules/employees, even though the URL is under the
// Employee resource — see modules/employees/api/employeeApi.ts's docstring
// on why: this is a User Management action, and keeping it here means
// neither module imports the other's internals.

export interface LinkableEmployee {
  id: string;
  fullName: string;
  employeeCode: string;
  userId: string | null;
}

interface EmployeeWireResponseForLinking {
  id: string;
  full_name: string;
  employee_code: string;
  user_id: string | null;
}

/**
 * A narrow, module-local fetch against `GET /api/v1/employees/` — only the
 * few fields the "Link to Employee" picker needs, not the full
 * `EmployeeResponseSerializer` shape `modules/employees` works with.
 */
export async function searchEmployeesForLinking(search: string): Promise<LinkableEmployee[]> {
  const response = await httpClient.get<ApiSuccessResponse<EmployeeWireResponseForLinking[]>>(
    `${API_ENDPOINTS.employees}/`,
    { params: { search: search || undefined, page_size: 25, ordering: "first_name,last_name" } },
  );
  return response.data.data.map((wire) => ({
    id: wire.id,
    fullName: wire.full_name,
    employeeCode: wire.employee_code,
    userId: wire.user_id,
  }));
}

/** `POST /api/v1/employees/{id}/link-user/` (Phase 12) */
export async function linkUserToEmployee(employeeId: string, userId: string): Promise<void> {
  await httpClient.post(`${API_ENDPOINTS.employees}/${employeeId}/link-user/`, { user_id: userId });
}

// --- Role assignment (Role & Permission Management phase) ---------------
// Lives here, not modules/users/api/roleApi.ts, even though the endpoints
// live under identity's `roles` vocabulary — same reasoning
// `linkUserToEmployee` above already established: this acts primarily on a
// *User* (which roles does this user hold), so it belongs with the other
// user-mutating calls. `roleApi.ts` stays scoped to the Role resource itself
// (CRUD + the permission catalogue).

/** `POST /api/v1/auth/users/{userId}/roles/` */
export async function assignRoleToUser(userId: string, roleId: string): Promise<void> {
  await httpClient.post(`${API_ENDPOINTS.auth}/users/${userId}/roles/`, { role_id: roleId });
}

/** `DELETE /api/v1/auth/users/{userId}/roles/{roleId}/` */
export async function revokeRoleFromUser(userId: string, roleId: string): Promise<void> {
  await httpClient.delete(`${API_ENDPOINTS.auth}/users/${userId}/roles/${roleId}/`);
}
