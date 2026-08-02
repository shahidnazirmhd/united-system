/**
 * Every route path in the application, in one place. No component should
 * ever hardcode a path string — always reference `ROUTE_PATHS` (for
 * navigation/links) or build off `DASHBOARD_NAV_ITEMS`
 * (layouts/DashboardLayout/navigation.ts) for sidebar entries. Adding a
 * future module's route means adding one entry here and one entry in
 * app/router/routes.tsx — nothing else needs to change.
 */
export const ROUTE_PATHS = {
  auth: {
    login: "/auth/login",
  },
  dashboard: {
    home: "/",
    employees: "/employees",
    employeesNew: "/employees/new",
    employeeDepartments: "/employees/departments",
    leave: "/leave",
    leaveTypes: "/leave/types",
    approvals: "/approvals",
    attendance: "/attendance",
    attendanceHolidays: "/attendance/holidays",
    assetRequests: "/asset-requests",
    notifications: "/notifications",
    users: "/users",
    userRoles: "/users/roles",
    settings: "/settings",
  },
} as const;

/**
 * Builders for routes with a dynamic `:id` segment — kept alongside
 * `ROUTE_PATHS` (not inlined at each call site) so the `/employees/:id`
 * shape only needs to change in one place. First need in this codebase as
 * of Phase 12 (Employee Details/Edit); `ROUTE_PATHS` itself stays a plain
 * string map since every other route so far had no params.
 */
export const buildEmployeeDetailPath = (employeeId: string): string => `/employees/${employeeId}`;
export const buildEmployeeEditPath = (employeeId: string): string => `/employees/${employeeId}/edit`;
export const buildLeaveRequestDetailPath = (leaveRequestId: string): string => `/leave/${leaveRequestId}`;
