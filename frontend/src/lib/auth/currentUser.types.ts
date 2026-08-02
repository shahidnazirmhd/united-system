/**
 * Mirrors IDENTITY_API.md's `GET /auth/me/` response (`UserSummarySerializer`),
 * camelCased — same convention as `modules/auth/types/auth.types.ts`'s
 * `AuthTokenPairResponse`. Lives in `lib/auth` (foundation), not
 * `modules/users`, because layouts (UserMenu) can never depend on a feature
 * module — see `useCurrentUserQuery.ts`'s docstring.
 */
export interface CurrentUserRole {
  id: string;
  name: string;
}

export interface CurrentUser {
  id: string;
  email: string;
  isActive: boolean;
  employeeId: string | null;
  roles: CurrentUserRole[];
  permissionCodes: string[];
}
