import { useMutation, useQueryClient, type UseMutationResult } from "@tanstack/react-query";

import type { ApiError } from "@/lib/api/types";
import { updateSetting } from "@/modules/settings/api/settingsApi";
import type { Setting } from "@/modules/settings/types/setting.types";

export function useUpdateSettingMutation(): UseMutationResult<
  Setting,
  ApiError,
  { key: string; value: unknown }
> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ key, value }) => updateSetting(key, value),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["settings"] });
    },
  });
}
