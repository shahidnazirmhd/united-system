/** Mirrors EMPLOYEE_API.md's Department CRUD `DepartmentResponseSerializer` (Phase 12), camelCased. */
export interface Department {
  id: string;
  name: string;
  code: string;
  parentDepartmentId: string | null;
  headEmployeeId: string | null;
  isActive: boolean;
  /** Resolved on single-record reads only — null on list rows. */
  parentDepartmentName: string | null;
  headEmployeeName: string | null;
}

export interface DepartmentListFilters {
  isActive?: boolean;
  search?: string;
  ordering?: string;
  page?: number;
  pageSize?: number;
}

export interface CreateDepartmentInput {
  name: string;
  code: string;
  parentDepartmentId: string | null;
  headEmployeeId: string | null;
}

export interface UpdateDepartmentInput {
  name: string;
  code: string;
  parentDepartmentId: string | null;
  headEmployeeId: string | null;
  isActive: boolean;
}
