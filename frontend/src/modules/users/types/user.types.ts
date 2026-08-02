/**
 * This module's own domain types — mirrors IDENTITY_API.md's
 * `UserSummarySerializer`, camelCased. Deliberately a separate type from
 * `lib/auth`'s `CurrentUser` even though the wire shape is identical today:
 * that one models "who am I" for the foundation layer (UserMenu), this one
 * models "a user I, as an admin, am managing" for this feature module — see
 * `modules/auth/types/auth.types.ts`'s docstring on why module types never
 * get imported by the foundation, and the reverse holds here too: this
 * module doesn't reach into `lib/auth`'s session type just because the
 * shape happens to match.
 *
 * `isSystemAccount`/`is_system_account` (originally part of this phase)
 * was removed after investigation found it had no functional effect
 * anywhere in the backend — see `IDENTITY_API.md`'s migration note
 * (0005_remove_is_system_account) for the full reasoning.
 */
export interface ManagedUserRole {
  id: string;
  name: string;
}

export interface ManagedUser {
  id: string;
  email: string;
  isActive: boolean;
  employeeId: string | null;
  roles: ManagedUserRole[];
  permissionCodes: string[];
}

export interface UserListFilters {
  isActive?: boolean;
  search?: string;
  ordering?: string;
  page?: number;
  pageSize?: number;
}

export interface CreateUserInput {
  email: string;
  password: string;
}

export interface UpdateUserInput {
  email: string;
}
