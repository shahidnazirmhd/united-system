import { API_ENDPOINTS } from "@/lib/api/endpoints";
import { httpClient } from "@/lib/api/httpClient";
import type { ApiSuccessResponse } from "@/lib/api/types";
import type { Setting } from "@/modules/settings/types/setting.types";

/** `GET /api/v1/settings/` */
export async function listSettings(): Promise<Setting[]> {
  const response = await httpClient.get<ApiSuccessResponse<Setting[]>>(`${API_ENDPOINTS.settings}/`);
  return response.data.data;
}

/** `PATCH /api/v1/settings/{key}/` */
export async function updateSetting(key: string, value: unknown): Promise<Setting> {
  const response = await httpClient.patch<ApiSuccessResponse<Setting>>(
    `${API_ENDPOINTS.settings}/${key}/`,
    { value },
  );
  return response.data.data;
}
