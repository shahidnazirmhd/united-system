import { useMutation, useQueryClient, type UseMutationResult } from "@tanstack/react-query";

import type { ApiError } from "@/lib/api/types";
import { createDepartment, updateDepartment } from "@/modules/employees/api/departmentApi";
import type {
  CreateDepartmentInput,
  Department,
  UpdateDepartmentInput,
} from "@/modules/employees/types/department.types";

export function useCreateDepartmentMutation(): UseMutationResult<
  Department,
  ApiError,
  CreateDepartmentInput
> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: createDepartment,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["departments"] });
    },
  });
}

export function useUpdateDepartmentMutation(): UseMutationResult<
  Department,
  ApiError,
  { departmentId: string; input: UpdateDepartmentInput }
> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ departmentId, input }) => updateDepartment(departmentId, input),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["departments"] });
    },
  });
}
