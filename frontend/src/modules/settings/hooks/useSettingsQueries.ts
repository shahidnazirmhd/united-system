import { useQuery, type UseQueryResult } from "@tanstack/react-query";

import type { ApiError } from "@/lib/api/types";
import { listSettings } from "@/modules/settings/api/settingsApi";
import type { Setting } from "@/modules/settings/types/setting.types";

export function useSettingsQuery(): UseQueryResult<Setting[], ApiError> {
  return useQuery({
    queryKey: ["settings", "list"],
    queryFn: listSettings,
  });
}
