import { Navigate, Outlet } from "react-router-dom";

import { ROUTE_PATHS } from "@/app/router/routePaths";
import { useAuth } from "@/lib/auth";

/**
 * Layout route guarding every dashboard-module route. Renders its children
 * (via `Outlet`) only when a valid session exists; otherwise redirects to
 * the login screen.
 *
 * Reactive by construction: because this component reads `useAuth()`, it
 * re-renders — and re-evaluates this check — the instant `AuthProvider`'s
 * state changes, e.g. when `useSignOut` clears the session, or httpClient's
 * silent-refresh-on-401 path gives up and emits a session-expired event. No
 * imperative `navigate()` call is needed anywhere else in the app for
 * either case.
 */
export function ProtectedRoute() {
  const { isAuthenticated } = useAuth();

  if (!isAuthenticated) {
    return <Navigate to={ROUTE_PATHS.auth.login} replace />;
  }

  return <Outlet />;
}
