import { useMutation, useQueryClient, type UseMutationResult } from "@tanstack/react-query";

import type { ApiError } from "@/lib/api/types";
import { createRole, deleteRole, updateRole } from "@/modules/users/api/roleApi";
import type { Role, RoleFormInput } from "@/modules/users/types/role.types";

export function useCreateRoleMutation(): UseMutationResult<Role, ApiError, RoleFormInput> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: createRole,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["roles"] });
    },
  });
}

export function useUpdateRoleMutation(): UseMutationResult<
  Role,
  ApiError,
  { roleId: string; input: RoleFormInput }
> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ roleId, input }) => updateRole(roleId, input),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["roles"] });
      // A role's permission_codes changing can change what an already-loaded
      // user's `permissionCodes` should be — invalidate both, matching how
      // useLinkUserToEmployeeMutation invalidates across module boundaries.
      void queryClient.invalidateQueries({ queryKey: ["users"] });
    },
  });
}

export function useDeleteRoleMutation(): UseMutationResult<void, ApiError, string> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: deleteRole,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["roles"] });
    },
  });
}
