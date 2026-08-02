/** Mirrors the backend's `HolidayResponseSerializer` (round 14 item 5), camelCased. */
export interface Holiday {
  id: string;
  name: string;
  holidayDate: string;
  description: string;
  isActive: boolean;
}

export interface HolidayListFilters {
  isActive?: boolean;
  year?: number;
  search?: string;
  ordering?: string;
  page?: number;
  pageSize?: number;
}

export interface CreateHolidayInput {
  name: string;
  holidayDate: string;
  description: string;
}

export interface UpdateHolidayInput {
  name: string;
  holidayDate: string;
  description: string;
  isActive: boolean;
}
