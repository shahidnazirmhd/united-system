import { useMutation, useQueryClient, type UseMutationResult } from "@tanstack/react-query";

import type { ApiError } from "@/lib/api/types";
import {
  activateEmployee,
  createEmployee,
  deactivateEmployee,
  updateEmployee,
  updateEmployeeCurrentStatus,
} from "@/modules/employees/api/employeeApi";
import type {
  CreateEmployeeInput,
  Employee,
  EmployeeCurrentStatus,
  UpdateEmployeeInput,
} from "@/modules/employees/types/employee.types";

export function useCreateEmployeeMutation(): UseMutationResult<
  Employee,
  ApiError,
  CreateEmployeeInput
> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: createEmployee,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["employees"] });
    },
  });
}

export function useUpdateEmployeeMutation(): UseMutationResult<
  Employee,
  ApiError,
  { employeeId: string; input: UpdateEmployeeInput }
> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ employeeId, input }) => updateEmployee(employeeId, input),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["employees"] });
    },
  });
}

export function useActivateEmployeeMutation(): UseMutationResult<Employee, ApiError, string> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: activateEmployee,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["employees"] });
    },
  });
}

export function useDeactivateEmployeeMutation(): UseMutationResult<Employee, ApiError, string> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: deactivateEmployee,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["employees"] });
    },
  });
}

export function useUpdateEmployeeCurrentStatusMutation(): UseMutationResult<
  Employee,
  ApiError,
  { employeeId: string; currentStatus: EmployeeCurrentStatus }
> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ employeeId, currentStatus }) => updateEmployeeCurrentStatus(employeeId, currentStatus),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["employees"] });
    },
  });
}
