import { Suspense, type LazyExoticComponent, type ReactElement } from "react";

import { PageLoader } from "@/components/common/PageLoader";

/**
 * Wraps a lazily-imported page component with a Suspense boundary and a
 * consistent loading fallback. This is the pattern every future module
 * should use for its own route-level page components, e.g.:
 *
 *   const EmployeeListPage = lazy(() => import("@/modules/employees/pages/EmployeeListPage"));
 *   ...
 *   { path: ROUTE_PATHS.dashboard.employees, element: withSuspense(EmployeeListPage) }
 *
 * Route-based code splitting keeps the initial bundle small as more modules
 * are added — each module's page code is only downloaded when its route is
 * actually visited.
 */
export function withSuspense(LazyComponent: LazyExoticComponent<() => ReactElement>): ReactElement {
  return (
    <Suspense fallback={<PageLoader />}>
      <LazyComponent />
    </Suspense>
  );
}
