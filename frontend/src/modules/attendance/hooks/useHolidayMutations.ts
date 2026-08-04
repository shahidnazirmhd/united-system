import { useMutation, useQueryClient, type UseMutationResult } from "@tanstack/react-query";

import type { ApiError } from "@/lib/api/types";
import { createHoliday, updateHoliday } from "@/modules/attendance/api/holidayApi";
import type {
  CreateHolidayInput,
  Holiday,
  UpdateHolidayInput,
} from "@/modules/attendance/types/holiday.types";

export function useCreateHolidayMutation(): UseMutationResult<
  Holiday,
  ApiError,
  CreateHolidayInput
> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: createHoliday,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["holidays"] });
    },
  });
}

export function useUpdateHolidayMutation(): UseMutationResult<
  Holiday,
  ApiError,
  { holidayId: string; input: UpdateHolidayInput }
> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ holidayId, input }) => updateHoliday(holidayId, input),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["holidays"] });
    },
  });
}
