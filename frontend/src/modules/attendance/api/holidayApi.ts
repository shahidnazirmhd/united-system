import { API_ENDPOINTS } from "@/lib/api/endpoints";
import { httpClient } from "@/lib/api/httpClient";
import type { ApiSuccessResponse, PagedResult } from "@/lib/api/types";
import type {
  CreateHolidayInput,
  Holiday,
  HolidayListFilters,
  UpdateHolidayInput,
} from "@/modules/attendance/types/holiday.types";

interface HolidayWireResponse {
  id: string;
  name: string;
  holiday_date: string;
  description: string;
  is_active: boolean;
}

function toHoliday(wire: HolidayWireResponse): Holiday {
  return {
    id: wire.id,
    name: wire.name,
    holidayDate: wire.holiday_date,
    description: wire.description,
    isActive: wire.is_active,
  };
}

/** `GET /api/v1/attendance/holidays/` */
export async function listHolidays(
  filters: HolidayListFilters = {},
): Promise<PagedResult<Holiday>> {
  const response = await httpClient.get<ApiSuccessResponse<HolidayWireResponse[]>>(
    `${API_ENDPOINTS.attendance}/holidays/`,
    {
      params: {
        is_active: filters.isActive,
        year: filters.year,
        search: filters.search || undefined,
        ordering: filters.ordering,
        page: filters.page,
        page_size: filters.pageSize,
      },
    },
  );
  return {
    items: response.data.data.map(toHoliday),
    meta: response.data.meta!,
  };
}

/** `POST /api/v1/attendance/holidays/` */
export async function createHoliday(input: CreateHolidayInput): Promise<Holiday> {
  const response = await httpClient.post<ApiSuccessResponse<HolidayWireResponse>>(
    `${API_ENDPOINTS.attendance}/holidays/`,
    {
      name: input.name,
      holiday_date: input.holidayDate,
      description: input.description,
    },
  );
  return toHoliday(response.data.data);
}

/** `PATCH /api/v1/attendance/holidays/{id}/` — full-replace update. */
export async function updateHoliday(
  holidayId: string,
  input: UpdateHolidayInput,
): Promise<Holiday> {
  const response = await httpClient.patch<ApiSuccessResponse<HolidayWireResponse>>(
    `${API_ENDPOINTS.attendance}/holidays/${holidayId}/`,
    {
      name: input.name,
      holiday_date: input.holidayDate,
      description: input.description,
      is_active: input.isActive,
    },
  );
  return toHoliday(response.data.data);
}
