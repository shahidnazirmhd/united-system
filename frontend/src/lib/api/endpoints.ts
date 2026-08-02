/**
 * Base path segments for each backend module, mirrored from the backend's
 * own `API_MODULE_URL_PREFIXES` (config/module_registry.py) and documented
 * per-module in IDENTITY_API.md / EMPLOYEE_API.md / LEAVE_API.md /
 * APPROVALS_API.md. This file intentionally stops at base paths — actual
 * request functions (e.g. `getEmployeeById`) belong inside each feature
 * module under src/modules/<module>/api, not here, so this foundation layer
 * never grows business logic.
 */
export const API_ENDPOINTS = {
  auth: "/auth",
  employees: "/employees",
  leave: "/leave",
  approvals: "/approvals",
  settings: "/settings",
  attendance: "/attendance",
} as const;
