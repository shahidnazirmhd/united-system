/**
 * Query-key factory convention every future module should follow (the
 * pattern popularized as "query key factories" in the TanStack Query
 * ecosystem) — it guarantees collision-free, consistent keys across every
 * module without each one hand-writing ad-hoc arrays. Example usage inside
 * a future module:
 *
 *   interface EmployeeListFilters { departmentId?: string; status?: string }
 *
 *   export const employeeKeys = createQueryKeyFactory<EmployeeListFilters>("employees");
 *
 *   employeeKeys.all            -> ["employees"]
 *   employeeKeys.lists()        -> ["employees", "list"]
 *   employeeKeys.list(filters)  -> ["employees", "list", filters]
 *   employeeKeys.details()      -> ["employees", "detail"]
 *   employeeKeys.detail(id)     -> ["employees", "detail", id]
 *
 * `employeeKeys.lists()` is what you invalidate after a create/update/delete
 * mutation — every list query, regardless of its filters, gets refetched.
 */
export interface QueryKeyFactory<TFilters> {
  all: readonly [string];
  lists: () => readonly [string, "list"];
  list: (filters: TFilters) => readonly [string, "list", TFilters];
  details: () => readonly [string, "detail"];
  detail: (id: string) => readonly [string, "detail", string];
}

export function createQueryKeyFactory<TFilters = void>(
  namespace: string,
): QueryKeyFactory<TFilters> {
  return {
    all: [namespace] as const,
    lists: () => [namespace, "list"] as const,
    list: (filters: TFilters) => [namespace, "list", filters] as const,
    details: () => [namespace, "detail"] as const,
    detail: (id: string) => [namespace, "detail", id] as const,
  };
}
