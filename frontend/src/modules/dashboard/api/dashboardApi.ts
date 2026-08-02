import { API_ENDPOINTS } from "@/lib/api/endpoints";
import { httpClient } from "@/lib/api/httpClient";
import type { ApiSuccessResponse } from "@/lib/api/types";
import type {
  EmployeeDepartmentStat,
  EmployeeStatistics,
  LeaveMonthlyStat,
  LeaveStatistics,
  LeaveTypeStat,
  RecentActivityItem,
  UpcomingHoliday,
} from "@/modules/dashboard/types/dashboard.types";

interface EmployeeDepartmentStatWireResponse {
  department_id: string;
  department_name: string;
  count: number;
}

interface EmployeeStatisticsWireResponse {
  total_employees: number;
  active_count: number;
  inactive_count: number;
  terminated_count: number;
  status_breakdown: Record<string, number>;
  current_status_breakdown: Record<string, number>;
  employment_type_breakdown: Record<string, number>;
  department_breakdown: EmployeeDepartmentStatWireResponse[];
  new_hires_this_month: number;
}

function toEmployeeStatistics(wire: EmployeeStatisticsWireResponse): EmployeeStatistics {
  return {
    totalEmployees: wire.total_employees,
    activeCount: wire.active_count,
    inactiveCount: wire.inactive_count,
    terminatedCount: wire.terminated_count,
    statusBreakdown: wire.status_breakdown,
    currentStatusBreakdown: wire.current_status_breakdown,
    employmentTypeBreakdown: wire.employment_type_breakdown,
    departmentBreakdown: wire.department_breakdown.map(
      (stat): EmployeeDepartmentStat => ({
        departmentId: stat.department_id,
        departmentName: stat.department_name,
        count: stat.count,
      }),
    ),
    newHiresThisMonth: wire.new_hires_this_month,
  };
}

interface LeaveTypeStatWireResponse {
  leave_type_id: string;
  leave_type_name: string;
  count: number;
}

interface LeaveMonthlyStatWireResponse {
  month: string;
  count: number;
}

interface LeaveStatisticsWireResponse {
  status_breakdown: Record<string, number>;
  leave_type_breakdown: LeaveTypeStatWireResponse[];
  monthly_trend: LeaveMonthlyStatWireResponse[];
  on_leave_today_count: number;
}

function toLeaveStatistics(wire: LeaveStatisticsWireResponse): LeaveStatistics {
  return {
    statusBreakdown: wire.status_breakdown,
    leaveTypeBreakdown: wire.leave_type_breakdown.map(
      (stat): LeaveTypeStat => ({
        leaveTypeId: stat.leave_type_id,
        leaveTypeName: stat.leave_type_name,
        count: stat.count,
      }),
    ),
    monthlyTrend: wire.monthly_trend.map((stat): LeaveMonthlyStat => ({ month: stat.month, count: stat.count })),
    onLeaveTodayCount: wire.on_leave_today_count,
  };
}

interface RecentActivityItemWireResponse {
  leave_request_id: string;
  employee_id: string;
  employee_name: string | null;
  employee_code: string | null;
  leave_type_name: string | null;
  status: string;
  start_date: string;
  end_date: string;
  updated_at: string | null;
}

function toRecentActivityItem(wire: RecentActivityItemWireResponse): RecentActivityItem {
  return {
    leaveRequestId: wire.leave_request_id,
    employeeId: wire.employee_id,
    employeeName: wire.employee_name,
    employeeCode: wire.employee_code,
    leaveTypeName: wire.leave_type_name,
    status: wire.status,
    startDate: wire.start_date,
    endDate: wire.end_date,
    updatedAt: wire.updated_at,
  };
}

interface UpcomingHolidayWireResponse {
  id: string;
  name: string;
  holiday_date: string;
  description: string;
}

function toUpcomingHoliday(wire: UpcomingHolidayWireResponse): UpcomingHoliday {
  return { id: wire.id, name: wire.name, holidayDate: wire.holiday_date, description: wire.description };
}

/** `GET /api/v1/dashboard/employee-statistics/` */
export async function getEmployeeStatistics(): Promise<EmployeeStatistics> {
  const response = await httpClient.get<ApiSuccessResponse<EmployeeStatisticsWireResponse>>(
    `${API_ENDPOINTS.dashboard}/employee-statistics/`,
  );
  return toEmployeeStatistics(response.data.data);
}

/** `GET /api/v1/dashboard/leave-statistics/` */
export async function getLeaveStatistics(): Promise<LeaveStatistics> {
  const response = await httpClient.get<ApiSuccessResponse<LeaveStatisticsWireResponse>>(
    `${API_ENDPOINTS.dashboard}/leave-statistics/`,
  );
  return toLeaveStatistics(response.data.data);
}

/** `GET /api/v1/dashboard/recent-activity/?limit=` */
export async function getRecentActivity(limit: number): Promise<RecentActivityItem[]> {
  const response = await httpClient.get<ApiSuccessResponse<RecentActivityItemWireResponse[]>>(
    `${API_ENDPOINTS.dashboard}/recent-activity/`,
    { params: { limit } },
  );
  return response.data.data.map(toRecentActivityItem);
}

/** `GET /api/v1/dashboard/upcoming-holidays/?limit=` */
export async function getUpcomingHolidays(limit: number): Promise<UpcomingHoliday[]> {
  const response = await httpClient.get<ApiSuccessResponse<UpcomingHolidayWireResponse[]>>(
    `${API_ENDPOINTS.dashboard}/upcoming-holidays/`,
    { params: { limit } },
  );
  return response.data.data.map(toUpcomingHoliday);
}
