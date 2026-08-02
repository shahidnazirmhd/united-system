import { useCurrentUserQuery } from "@/lib/auth/useCurrentUserQuery";

/**
 * Foundation-level permission check, built on the same `GET /auth/me/`
 * data every module already fetches via `useCurrentUserQuery` — lives in
 * `lib/auth` (not `modules/users`) for the same reason `useCurrentUserQuery`
 * itself does: layouts (Sidebar) and every feature module need this without
 * depending on the Users module (FRONTEND_ARCHITECTURE.md's dependency
 * rule — layouts/foundation never import from `modules/*`).
 *
 * Role & Permission Management review round: this reverses the earlier
 * "no client-side nav/route gating exists anywhere, the page itself decides
 * access" precedent (see LeaveDashboardPage.tsx's older docstring) — that
 * precedent under-served a real requirement (a user should not even SEE a
 * module they can't use, not just be blocked once they click into it) and
 * was called out explicitly as a bug. Every module's nav item, page-level
 * gate, and destructive/mutating action should now use these hooks instead
 * of duplicating `currentUser?.permissionCodes.includes(...)` inline.
 *
 * This is a client-side convenience only — hiding a button or nav item never
 * substitutes for the backend's own `HasPermission` check on the endpoint
 * itself (every mutating/viewing endpoint in this codebase already enforces
 * that; see IDENTITY_API.md). A user who never sees "New User" still can't
 * force it by hitting the API directly, because the server checks again.
 *
 * While `useCurrentUserQuery` is loading (or for an unauthenticated caller),
 * these hooks conservatively return `false` rather than `true` — a
 * momentarily-hidden action while the profile loads is a much smaller
 * problem than a flash of a button the caller turns out not to be allowed
 * to use.
 */
export function useHasPermission(permissionCode: string): boolean {
  const { data: currentUser } = useCurrentUserQuery();
  return currentUser?.permissionCodes.includes(permissionCode) ?? false;
}

/** True if the caller holds ANY of the given permission codes — the shape
 * every nav item and page-level gate actually needs (e.g. Leave's tab is
 * visible to `leave.view_leave` OR `leave.manage_leave` holders). An empty
 * `codes` array means "no permission required," matching how
 * `DASHBOARD_NAV_ITEMS`'s items with no `anyOfPermissions` behave. */
export function useHasAnyPermission(codes: readonly string[]): boolean {
  const { data: currentUser } = useCurrentUserQuery();
  if (codes.length === 0) {
    return true;
  }
  const held = currentUser?.permissionCodes;
  if (!held) {
    return false;
  }
  return codes.some((code) => held.includes(code));
}
