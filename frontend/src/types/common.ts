/**
 * Cross-cutting types with no natural home in any single future module.
 * Module-specific types (an `Employee`, a `LeaveRequest`) belong inside
 * that module's own `types.ts` under src/modules/<module>, never here.
 */
export interface PaginationMeta {
  page: number;
  pageSize: number;
  totalCount: number;
  totalPages: number;
}

export interface SelectOption<TValue = string> {
  label: string;
  value: TValue;
}

export type SortDirection = "asc" | "desc";

export interface SortState<TField extends string = string> {
  field: TField;
  direction: SortDirection;
}
