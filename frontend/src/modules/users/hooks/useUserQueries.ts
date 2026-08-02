import { useQuery, type UseQueryResult } from "@tanstack/react-query";

import type { ApiError, PagedResult } from "@/lib/api/types";
import { getUserById, listUsers, searchEmployeesForLinking } from "@/modules/users/api/userApi";
import type { ManagedUser, UserListFilters } from "@/modules/users/types/user.types";
import type { LinkableEmployee } from "@/modules/users/api/userApi";

export function useUsersQuery(filters: UserListFilters): UseQueryResult<PagedResult<ManagedUser>, ApiError> {
  return useQuery({
    queryKey: ["users", "list", filters],
    queryFn: () => listUsers(filters),
    placeholderData: (previousData) => previousData,
  });
}

export function useUserQuery(userId: string | undefined): UseQueryResult<ManagedUser, ApiError> {
  return useQuery({
    queryKey: ["users", "detail", userId],
    queryFn: () => getUserById(userId as string),
    enabled: Boolean(userId),
  });
}

/** Feeds the "Link to Employee" dialog's search-as-you-type employee picker. */
export function useLinkableEmployeesQuery(search: string): UseQueryResult<LinkableEmployee[], ApiError> {
  return useQuery({
    queryKey: ["employees", "linkable", search],
    queryFn: () => searchEmployeesForLinking(search),
    staleTime: 30_000,
  });
}
