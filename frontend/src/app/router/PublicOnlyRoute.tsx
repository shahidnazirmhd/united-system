import { Navigate, Outlet } from "react-router-dom";

import { ROUTE_PATHS } from "@/app/router/routePaths";
import { useAuth } from "@/lib/auth";

/**
 * Inverse of ProtectedRoute — guards routes that only make sense for a
 * signed-out visitor (currently just /auth/login). An already-authenticated
 * user landing here (browser back button, a stale bookmark) is sent
 * straight to the dashboard instead of seeing the login form again.
 *
 * This is also what makes a successful login redirect to the dashboard
 * without `LoginForm` ever calling `navigate()` itself: once
 * `useAuth().login()` flips `isAuthenticated` to true, this component
 * re-renders and swaps from `Outlet` to `Navigate` on its own.
 */
export function PublicOnlyRoute() {
  const { isAuthenticated } = useAuth();

  if (isAuthenticated) {
    return <Navigate to={ROUTE_PATHS.dashboard.home} replace />;
  }

  return <Outlet />;
}
