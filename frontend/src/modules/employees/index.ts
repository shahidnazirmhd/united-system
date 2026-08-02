/**
 * Public surface of the employees module — the only things other code (the
 * router) is allowed to import from this module, same convention
 * `modules/auth/index.ts` established. Everything else (api/, hooks/,
 * validation/, components/, types/) is an internal implementation detail.
 */
export { DepartmentsPage } from "@/modules/employees/pages/DepartmentsPage";
export { EmployeeCreatePage } from "@/modules/employees/pages/EmployeeCreatePage";
export { EmployeeDetailPage } from "@/modules/employees/pages/EmployeeDetailPage";
export { EmployeeEditPage } from "@/modules/employees/pages/EmployeeEditPage";
export { EmployeeListPage } from "@/modules/employees/pages/EmployeeListPage";
