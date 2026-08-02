import { API_ENDPOINTS } from "@/lib/api/endpoints";
import { httpClient } from "@/lib/api/httpClient";
import type { ApiSuccessResponse, PagedResult } from "@/lib/api/types";
import type {
  CreateEmployeeInput,
  Employee,
  EmployeeCurrentStatus,
  EmployeeListFilters,
  EmploymentType,
  EmployeeStatus,
  UpdateEmployeeInput,
} from "@/modules/employees/types/employee.types";

/** The exact wire shape EMPLOYEE_API.md documents for `EmployeeResponseSerializer`. */
interface EmployeeWireResponse {
  id: string;
  employee_code: string;
  user_id: string | null;
  first_name: string;
  last_name: string;
  full_name: string;
  date_of_birth: string | null;
  gender: string | null;
  work_email: string;
  personal_email: string | null;
  phone_number: string | null;
  department_id: string;
  manager_id: string | null;
  job_title: string;
  employment_type: EmploymentType;
  date_of_joining: string;
  last_working_date: string | null; // round 15 item 9 — renamed from termination_date
  status: EmployeeStatus;
  department_name: string | null;
  manager_name: string | null;
  linked_user_email: string | null;
  is_linked_to_telegram: boolean;
  telegram_username: string | null;
  telegram_linked_at: string | null;
  current_status: EmployeeCurrentStatus;
  status_before_leave: EmployeeCurrentStatus | null;
  is_eligible_for_leave: boolean;
}

function toEmployee(wire: EmployeeWireResponse): Employee {
  return {
    id: wire.id,
    employeeCode: wire.employee_code,
    userId: wire.user_id,
    firstName: wire.first_name,
    lastName: wire.last_name,
    fullName: wire.full_name,
    dateOfBirth: wire.date_of_birth,
    gender: wire.gender,
    workEmail: wire.work_email,
    personalEmail: wire.personal_email,
    phoneNumber: wire.phone_number,
    departmentId: wire.department_id,
    managerId: wire.manager_id,
    jobTitle: wire.job_title,
    employmentType: wire.employment_type,
    dateOfJoining: wire.date_of_joining,
    lastWorkingDate: wire.last_working_date,
    status: wire.status,
    departmentName: wire.department_name,
    managerName: wire.manager_name,
    linkedUserEmail: wire.linked_user_email,
    isLinkedToTelegram: wire.is_linked_to_telegram,
    telegramUsername: wire.telegram_username,
    telegramLinkedAt: wire.telegram_linked_at,
    currentStatus: wire.current_status,
    statusBeforeLeave: wire.status_before_leave,
    isEligibleForLeave: wire.is_eligible_for_leave,
  };
}

/** `GET /api/v1/employees/` — list, with filter/search/ordering/pagination. */
export async function listEmployees(filters: EmployeeListFilters): Promise<PagedResult<Employee>> {
  const response = await httpClient.get<ApiSuccessResponse<EmployeeWireResponse[]>>(
    `${API_ENDPOINTS.employees}/`,
    {
      params: {
        department_id: filters.departmentId,
        employment_status: filters.employmentStatus,
        employment_type: filters.employmentType,
        search: filters.search || undefined,
        ordering: filters.ordering,
        page: filters.page,
        page_size: filters.pageSize,
      },
    },
  );
  return {
    items: response.data.data.map(toEmployee),
    // meta is always present on list endpoints — see PaginationMetaResponse's docstring.
    meta: response.data.meta!,
  };
}

/** `GET /api/v1/employees/{id}/` */
export async function getEmployeeById(employeeId: string): Promise<Employee> {
  const response = await httpClient.get<ApiSuccessResponse<EmployeeWireResponse>>(
    `${API_ENDPOINTS.employees}/${employeeId}/`,
  );
  return toEmployee(response.data.data);
}

/** `POST /api/v1/employees/` */
export async function createEmployee(input: CreateEmployeeInput): Promise<Employee> {
  const response = await httpClient.post<ApiSuccessResponse<EmployeeWireResponse>>(
    `${API_ENDPOINTS.employees}/`,
    {
      first_name: input.firstName,
      last_name: input.lastName,
      date_of_birth: input.dateOfBirth,
      gender: input.gender,
      work_email: input.workEmail,
      personal_email: input.personalEmail,
      phone_number: input.phoneNumber,
      department_id: input.departmentId,
      manager_id: input.managerId,
      job_title: input.jobTitle,
      employment_type: input.employmentType,
      date_of_joining: input.dateOfJoining,
      user_id: input.userId,
    },
  );
  return toEmployee(response.data.data);
}

/** `PATCH /api/v1/employees/{id}/` — full-replace update, see EMPLOYEE_API.md. */
export async function updateEmployee(
  employeeId: string,
  input: UpdateEmployeeInput,
): Promise<Employee> {
  const response = await httpClient.patch<ApiSuccessResponse<EmployeeWireResponse>>(
    `${API_ENDPOINTS.employees}/${employeeId}/`,
    {
      first_name: input.firstName,
      last_name: input.lastName,
      date_of_birth: input.dateOfBirth,
      gender: input.gender,
      work_email: input.workEmail,
      personal_email: input.personalEmail,
      phone_number: input.phoneNumber,
      department_id: input.departmentId,
      manager_id: input.managerId,
      job_title: input.jobTitle,
      employment_type: input.employmentType,
      date_of_joining: input.dateOfJoining,
      last_working_date: input.lastWorkingDate,
    },
  );
  return toEmployee(response.data.data);
}

/** `POST /api/v1/employees/{id}/activate/` */
export async function activateEmployee(employeeId: string): Promise<Employee> {
  const response = await httpClient.post<ApiSuccessResponse<EmployeeWireResponse>>(
    `${API_ENDPOINTS.employees}/${employeeId}/activate/`,
  );
  return toEmployee(response.data.data);
}

/** `POST /api/v1/employees/{id}/deactivate/` */
export async function deactivateEmployee(employeeId: string): Promise<Employee> {
  const response = await httpClient.post<ApiSuccessResponse<EmployeeWireResponse>>(
    `${API_ENDPOINTS.employees}/${employeeId}/deactivate/`,
  );
  return toEmployee(response.data.data);
}

/** `POST /api/v1/employees/{id}/current-status/` — round 14 item 8. */
export async function updateEmployeeCurrentStatus(
  employeeId: string,
  currentStatus: EmployeeCurrentStatus,
): Promise<Employee> {
  const response = await httpClient.post<ApiSuccessResponse<EmployeeWireResponse>>(
    `${API_ENDPOINTS.employees}/${employeeId}/current-status/`,
    { current_status: currentStatus },
  );
  return toEmployee(response.data.data);
}

// Note: `POST /api/v1/employees/{id}/link-user/` (Phase 12, User Management)
// is NOT here despite living under the Employee resource's URL — that
// action is triggered from the Users module's UI ("Link to Employee" on a
// User row), and modules/users calls it directly
// (modules/users/api/userApi.ts) rather than importing this file, keeping
// the two modules independent of each other (per this project's "always
// keep modules independent" rule) at the cost of one small duplicated
// fetch-employees-for-a-picker helper — see that file's docstring.
