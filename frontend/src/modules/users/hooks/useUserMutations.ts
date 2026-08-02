import { useMutation, useQueryClient, type UseMutationResult } from "@tanstack/react-query";

import type { ApiError } from "@/lib/api/types";
import {
  activateUser,
  assignRoleToUser,
  createUser,
  deactivateUser,
  linkUserToEmployee,
  requestPasswordResetForUser,
  revokeRoleFromUser,
  updateUser,
} from "@/modules/users/api/userApi";
import type { CreateUserInput, ManagedUser, UpdateUserInput } from "@/modules/users/types/user.types";

export function useCreateUserMutation(): UseMutationResult<ManagedUser, ApiError, CreateUserInput> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: createUser,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["users"] });
    },
  });
}

export function useUpdateUserMutation(): UseMutationResult<
  ManagedUser,
  ApiError,
  { userId: string; input: UpdateUserInput }
> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ userId, input }) => updateUser(userId, input),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["users"] });
    },
  });
}

export function useActivateUserMutation(): UseMutationResult<ManagedUser, ApiError, string> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: activateUser,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["users"] });
    },
  });
}

export function useDeactivateUserMutation(): UseMutationResult<ManagedUser, ApiError, string> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: deactivateUser,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["users"] });
    },
  });
}

export function useRequestPasswordResetMutation(): UseMutationResult<void, ApiError, string> {
  return useMutation({
    mutationFn: requestPasswordResetForUser,
  });
}

export function useLinkUserToEmployeeMutation(): UseMutationResult<
  void,
  ApiError,
  { employeeId: string; userId: string }
> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ employeeId, userId }) => linkUserToEmployee(employeeId, userId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["users"] });
      void queryClient.invalidateQueries({ queryKey: ["employees"] });
    },
  });
}

// --- Role assignment (Role & Permission Management phase) ---------------

export function useAssignRoleMutation(): UseMutationResult<
  void,
  ApiError,
  { userId: string; roleId: string }
> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ userId, roleId }) => assignRoleToUser(userId, roleId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["users"] });
    },
  });
}

export function useRevokeRoleMutation(): UseMutationResult<
  void,
  ApiError,
  { userId: string; roleId: string }
> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ userId, roleId }) => revokeRoleFromUser(userId, roleId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["users"] });
    },
  });
}

interface SyncUserRolesInput {
  userId: string;
  addRoleIds: string[];
  removeRoleIds: string[];
}

/**
 * Diffs a user's role selection against what they currently hold and fires
 * exactly the assign/revoke calls needed — there is no single "set a user's
 * roles" backend endpoint (each assign/revoke is its own auditable action,
 * see `AssignRoleToUserUseCase`/`RevokeRoleFromUserUseCase`'s own
 * `RoleAssignedToUser`/`RoleRevokedFromUser` events), so `EditUserDialog`
 * composes this from the two existing endpoints rather than the backend
 * gaining a bespoke bulk-replace one just for this dialog's convenience.
 */
export function useSyncUserRolesMutation(): UseMutationResult<void, ApiError, SyncUserRolesInput> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ userId, addRoleIds, removeRoleIds }) => {
      await Promise.all([
        ...addRoleIds.map((roleId) => assignRoleToUser(userId, roleId)),
        ...removeRoleIds.map((roleId) => revokeRoleFromUser(userId, roleId)),
      ]);
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["users"] });
    },
  });
}

interface CreateUserWithAssignmentsInput extends CreateUserInput {
  employeeId: string | null;
  roleIds: string[];
}

/**
 * Composes three separate backend calls behind one submit for the Create
 * User dialog's "optionally link an employee, optionally assign roles"
 * requirement: `createUser`, then (if chosen) `linkUserToEmployee`, then
 * (for each chosen role) `assignRoleToUser`. Deliberately sequential, not
 * `Promise.all`, since linking/role-assignment both need the id `createUser`
 * only returns after it resolves. Each backend endpoint keeps its own single
 * responsibility (see this phase's architecture note on Employee still
 * owning the link write and role assignment staying its own endpoint) — the
 * orchestration lives here, in the frontend's mutation layer, not by adding
 * a bespoke composite endpoint.
 */
export function useCreateUserWithAssignmentsMutation(): UseMutationResult<
  ManagedUser,
  ApiError,
  CreateUserWithAssignmentsInput
> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ employeeId, roleIds, ...input }) => {
      const user = await createUser(input);
      if (employeeId) {
        await linkUserToEmployee(employeeId, user.id);
      }
      for (const roleId of roleIds) {
        await assignRoleToUser(user.id, roleId);
      }
      return user;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["users"] });
      void queryClient.invalidateQueries({ queryKey: ["employees"] });
    },
  });
}
