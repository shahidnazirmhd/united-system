import { useQuery, type UseQueryResult } from "@tanstack/react-query";

import { API_ENDPOINTS } from "@/lib/api/endpoints";
import { httpClient } from "@/lib/api/httpClient";
import type { ApiError, ApiSuccessResponse } from "@/lib/api/types";
import type { CurrentUser } from "@/lib/auth/currentUser.types";
import { useAuth } from "@/lib/auth/useAuth";

interface CurrentUserWireResponse {
  id: string;
  email: string;
  is_active: boolean;
  employee_id: string | null;
  roles: { id: string; name: string }[];
  permission_codes: string[];
}

async function fetchCurrentUser(): Promise<CurrentUser> {
  const response = await httpClient.get<ApiSuccessResponse<CurrentUserWireResponse>>(
    `${API_ENDPOINTS.auth}/me/`,
  );
  const data = response.data.data;
  return {
    id: data.id,
    email: data.email,
    isActive: data.is_active,
    employeeId: data.employee_id,
    roles: data.roles,
    permissionCodes: data.permission_codes,
  };
}

/**
 * Fetches the authenticated caller's own profile (IDENTITY_API.md's
 * `GET /auth/me/`) — deliberately placed in `lib/auth` (foundation), not
 * `modules/users`, mirroring `useSignOut.ts`'s precedent of the foundation
 * layer owning session-adjacent Identity endpoints directly rather than
 * routing every consumer through a feature module.
 * `layouts/DashboardLayout/components/UserMenu.tsx` needs the caller's own
 * name/email, and layouts must never import from `modules/*`
 * (FRONTEND_ARCHITECTURE.md's dependency rule — see
 * `modules/auth/types/auth.types.ts`'s docstring for the same rule stated
 * the other direction). `modules/users`' own admin screens (List/Create/
 * Edit/Activate/Deactivate *other* users) are a distinct, larger feature and
 * correctly live in their own module — this hook is only for "who am I."
 *
 * `enabled: isAuthenticated` avoids firing this on the public Login route,
 * where there is no token to send yet.
 */
export function useCurrentUserQuery(): UseQueryResult<CurrentUser, ApiError> {
  const { isAuthenticated } = useAuth();

  return useQuery({
    queryKey: ["currentUser"],
    queryFn: fetchCurrentUser,
    enabled: isAuthenticated,
    staleTime: 60_000,
  });
}
