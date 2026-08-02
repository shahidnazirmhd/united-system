import { API_ENDPOINTS } from "@/lib/api/endpoints";
import { httpClient } from "@/lib/api/httpClient";
import type { ApiSuccessResponse, PagedResult } from "@/lib/api/types";
import type {
  CreateDepartmentInput,
  Department,
  DepartmentListFilters,
  UpdateDepartmentInput,
} from "@/modules/employees/types/department.types";

/** The exact wire shape EMPLOYEE_API.md's Department CRUD section documents. */
interface DepartmentWireResponse {
  id: string;
  name: string;
  code: string;
  parent_department_id: string | null;
  head_employee_id: string | null;
  is_active: boolean;
  parent_department_name: string | null;
  head_employee_name: string | null;
}

function toDepartment(wire: DepartmentWireResponse): Department {
  return {
    id: wire.id,
    name: wire.name,
    code: wire.code,
    parentDepartmentId: wire.parent_department_id,
    headEmployeeId: wire.head_employee_id,
    isActive: wire.is_active,
    parentDepartmentName: wire.parent_department_name,
    headEmployeeName: wire.head_employee_name,
  };
}

/** `GET /api/v1/employees/departments/` */
export async function listDepartments(
  filters: DepartmentListFilters = {},
): Promise<PagedResult<Department>> {
  const response = await httpClient.get<ApiSuccessResponse<DepartmentWireResponse[]>>(
    `${API_ENDPOINTS.employees}/departments/`,
    {
      params: {
        is_active: filters.isActive,
        search: filters.search || undefined,
        ordering: filters.ordering,
        page: filters.page,
        page_size: filters.pageSize,
      },
    },
  );
  return {
    items: response.data.data.map(toDepartment),
    meta: response.data.meta!,
  };
}

/** `GET /api/v1/employees/departments/{id}/` */
export async function getDepartmentById(departmentId: string): Promise<Department> {
  const response = await httpClient.get<ApiSuccessResponse<DepartmentWireResponse>>(
    `${API_ENDPOINTS.employees}/departments/${departmentId}/`,
  );
  return toDepartment(response.data.data);
}

/** `POST /api/v1/employees/departments/` */
export async function createDepartment(input: CreateDepartmentInput): Promise<Department> {
  const response = await httpClient.post<ApiSuccessResponse<DepartmentWireResponse>>(
    `${API_ENDPOINTS.employees}/departments/`,
    {
      name: input.name,
      code: input.code,
      parent_department_id: input.parentDepartmentId,
      head_employee_id: input.headEmployeeId,
    },
  );
  return toDepartment(response.data.data);
}

/** `PATCH /api/v1/employees/departments/{id}/` — full-replace update. */
export async function updateDepartment(
  departmentId: string,
  input: UpdateDepartmentInput,
): Promise<Department> {
  const response = await httpClient.patch<ApiSuccessResponse<DepartmentWireResponse>>(
    `${API_ENDPOINTS.employees}/departments/${departmentId}/`,
    {
      name: input.name,
      code: input.code,
      parent_department_id: input.parentDepartmentId,
      head_employee_id: input.headEmployeeId,
      is_active: input.isActive,
    },
  );
  return toDepartment(response.data.data);
}
