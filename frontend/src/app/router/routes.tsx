import { lazy } from "react";

import { createBrowserRouter } from "react-router-dom";

import { RouteErrorBoundary } from "@/app/error/RouteErrorBoundary";
import { ProtectedRoute } from "@/app/router/ProtectedRoute";
import { PublicOnlyRoute } from "@/app/router/PublicOnlyRoute";
import { ROUTE_PATHS } from "@/app/router/routePaths";
import { withSuspense } from "@/app/router/withSuspense";
import { AuthLayout } from "@/layouts/AuthLayout";
import { DashboardLayout } from "@/layouts/DashboardLayout";
import { MinimalLayout } from "@/layouts/MinimalLayout";
import { NotFoundPage } from "@/pages/NotFoundPage";
import { PlaceholderPage } from "@/pages/PlaceholderPage";

// Lazy-loaded as a worked example of the route-based code-splitting
// convention documented in withSuspense.tsx — every future module's page
// should follow this same `lazy(() => import(...))` pattern.
const DashboardHomePage = lazy(() =>
  import("@/pages/DashboardHomePage").then((module) => ({ default: module.DashboardHomePage })),
);

// Phase 11's first real module page — same lazy-loading convention as
// DashboardHomePage above, just living under src/modules/auth instead of
// src/pages since Login is a real feature, not a route placeholder.
const LoginPage = lazy(() =>
  import("@/modules/auth").then((module) => ({ default: module.LoginPage })),
);

// Phase 12 — Employee & User Management. Same lazy-loading convention,
// each page pulled from its module's public barrel (never a deep import).
const EmployeeListPage = lazy(() =>
  import("@/modules/employees").then((module) => ({ default: module.EmployeeListPage })),
);
const EmployeeCreatePage = lazy(() =>
  import("@/modules/employees").then((module) => ({ default: module.EmployeeCreatePage })),
);
const EmployeeDetailPage = lazy(() =>
  import("@/modules/employees").then((module) => ({ default: module.EmployeeDetailPage })),
);
const EmployeeEditPage = lazy(() =>
  import("@/modules/employees").then((module) => ({ default: module.EmployeeEditPage })),
);
const DepartmentsPage = lazy(() =>
  import("@/modules/employees").then((module) => ({ default: module.DepartmentsPage })),
);
const UserListPage = lazy(() =>
  import("@/modules/users").then((module) => ({ default: module.UserListPage })),
);
// Role & Permission Management phase — a sub-view of Users, same
// lazy-loading convention, mirrors DepartmentsPage's placement under Employees.
const RolesPage = lazy(() => import("@/modules/users").then((module) => ({ default: module.RolesPage })));

// Phase 13 — Leave Management + Approvals. Same lazy-loading convention.
const LeaveDashboardPage = lazy(() =>
  import("@/modules/leave").then((module) => ({ default: module.LeaveDashboardPage })),
);
const LeaveRequestDetailPage = lazy(() =>
  import("@/modules/leave").then((module) => ({ default: module.LeaveRequestDetailPage })),
);
// Sub-view of Leave, same placement convention as DepartmentsPage/RolesPage.
const LeaveTypesPage = lazy(() =>
  import("@/modules/leave").then((module) => ({ default: module.LeaveTypesPage })),
);
const ApprovalsPage = lazy(() =>
  import("@/modules/approvals").then((module) => ({ default: module.ApprovalsPage })),
);

// Round 14 — Settings + Attendance/Holiday Management. Same lazy-loading convention.
const AttendanceHomePage = lazy(() =>
  import("@/modules/attendance").then((module) => ({ default: module.AttendanceHomePage })),
);
// Sub-view of Attendance, same placement convention as DepartmentsPage/RolesPage.
const HolidayManagementPage = lazy(() =>
  import("@/modules/attendance").then((module) => ({ default: module.HolidayManagementPage })),
);
const SettingsPage = lazy(() =>
  import("@/modules/settings").then((module) => ({ default: module.SettingsPage })),
);

/**
 * The full route tree. Deliberately flat and declarative — each entry maps
 * one URL to one page component, nested under exactly one of the three
 * reusable layouts (Auth/Dashboard/Minimal). The dashboard tree sits behind
 * `ProtectedRoute`; the auth tree sits behind `PublicOnlyRoute` — see those
 * two files for why that alone is enough to redirect on login/logout with
 * no imperative `navigate()` calls anywhere. Employees/Users (Phase 12) are
 * real lazy-loaded pages now; every other dashboard-module route below
 * still renders the generic `PlaceholderPage` until that module's own phase
 * replaces it — see FRONTEND_ARCHITECTURE.md's "Adding a new module"
 * section. Departments has no sidebar entry of its own — it's reached only
 * via the Employee List page's header action (see
 * `modules/employees/pages/EmployeeListPage.tsx`).
 */
export const router = createBrowserRouter([
  {
    element: <ProtectedRoute />,
    errorElement: <RouteErrorBoundary />,
    children: [
      {
        element: <DashboardLayout />,
        children: [
          { index: true, element: withSuspense(DashboardHomePage) },
          {
            path: ROUTE_PATHS.dashboard.employees.slice(1),
            element: withSuspense(EmployeeListPage),
          },
          {
            path: ROUTE_PATHS.dashboard.employeesNew.slice(1),
            element: withSuspense(EmployeeCreatePage),
          },
          {
            path: ROUTE_PATHS.dashboard.employeeDepartments.slice(1),
            element: withSuspense(DepartmentsPage),
          },
          {
            path: "employees/:employeeId",
            element: withSuspense(EmployeeDetailPage),
          },
          {
            path: "employees/:employeeId/edit",
            element: withSuspense(EmployeeEditPage),
          },
          {
            path: ROUTE_PATHS.dashboard.users.slice(1),
            element: withSuspense(UserListPage),
          },
          {
            path: ROUTE_PATHS.dashboard.userRoles.slice(1),
            element: withSuspense(RolesPage),
          },
          {
            path: ROUTE_PATHS.dashboard.leave.slice(1),
            element: withSuspense(LeaveDashboardPage),
          },
          {
            path: ROUTE_PATHS.dashboard.leaveTypes.slice(1),
            element: withSuspense(LeaveTypesPage),
          },
          {
            path: "leave/:leaveRequestId",
            element: withSuspense(LeaveRequestDetailPage),
          },
          {
            path: ROUTE_PATHS.dashboard.approvals.slice(1),
            element: withSuspense(ApprovalsPage),
          },
          {
            path: ROUTE_PATHS.dashboard.attendance.slice(1),
            element: withSuspense(AttendanceHomePage),
          },
          {
            path: ROUTE_PATHS.dashboard.attendanceHolidays.slice(1),
            element: withSuspense(HolidayManagementPage),
          },
          {
            path: ROUTE_PATHS.dashboard.assetRequests.slice(1),
            element: (
              <PlaceholderPage
                title="Asset Requests"
                description="Asset request and issuance tracking will live here."
              />
            ),
          },
          {
            path: ROUTE_PATHS.dashboard.notifications.slice(1),
            element: (
              <PlaceholderPage
                title="Notifications"
                description="Notification history and preferences will live here."
              />
            ),
          },
          {
            path: ROUTE_PATHS.dashboard.settings.slice(1),
            element: withSuspense(SettingsPage),
          },
        ],
      },
    ],
  },
  {
    element: <PublicOnlyRoute />,
    errorElement: <RouteErrorBoundary />,
    children: [
      {
        element: <AuthLayout />,
        children: [{ path: ROUTE_PATHS.auth.login.slice(1), element: withSuspense(LoginPage) }],
      },
    ],
  },
  {
    path: "*",
    element: <MinimalLayout />,
    errorElement: <RouteErrorBoundary />,
    children: [{ index: true, element: <NotFoundPage /> }],
  },
]);
