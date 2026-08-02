/**
 * This module's own domain types — mirror the backend's `apps.dashboard`
 * DTOs (see `backend/apps/dashboard/application/dtos.py`) exactly,
 * camelCased. Deliberately NOT re-exports of Employees'/Leave's/
 * Attendance's own module types, even though the shapes overlap — Dashboard
 * is a pure read-aggregator with its own contract (see that Python file's
 * docstring for the full reasoning); each source module's own frontend
 * `modules/<name>/types` file remains that module's own concern.
 */

// --- Employee Statistics -------------------------------------------------

export interface EmployeeDepartmentStat {
  departmentId: string;
  departmentName: string;
  count: number;
}

export interface EmployeeStatistics {
  totalEmployees: number;
  activeCount: number;
  inactiveCount: number;
  terminatedCount: number;
  statusBreakdown: Record<string, number>;
  currentStatusBreakdown: Record<string, number>;
  employmentTypeBreakdown: Record<string, number>;
  departmentBreakdown: EmployeeDepartmentStat[];
  newHiresThisMonth: number;
}

// --- Leave Statistics -----------------------------------------------------

export interface LeaveTypeStat {
  leaveTypeId: string;
  leaveTypeName: string;
  count: number;
}

export interface LeaveMonthlyStat {
  month: string; // "YYYY-MM"
  count: number;
}

export interface LeaveStatistics {
  statusBreakdown: Record<string, number>;
  leaveTypeBreakdown: LeaveTypeStat[];
  monthlyTrend: LeaveMonthlyStat[];
  onLeaveTodayCount: number;
}

// --- Recent Activity --------------------------------------------------

export interface RecentActivityItem {
  leaveRequestId: string;
  employeeId: string;
  employeeName: string | null;
  employeeCode: string | null;
  leaveTypeName: string | null;
  status: string;
  startDate: string;
  endDate: string;
  updatedAt: string | null;
}

// --- Upcoming Holidays --------------------------------------------------

export interface UpcomingHoliday {
  id: string;
  name: string;
  holidayDate: string;
  description: string;
}

/** A generic `{name, value}` point — the shape every chart component in
 * this module accepts, so a future widget can feed it any breakdown
 * (department, leave type, employment type, ...) without a bespoke prop
 * shape per chart. */
export interface ChartDatum {
  name: string;
  value: number;
}
