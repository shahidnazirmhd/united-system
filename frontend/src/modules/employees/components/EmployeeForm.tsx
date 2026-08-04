import { zodResolver } from "@hookform/resolvers/zod";
import { Loader2 } from "lucide-react";
import { useState } from "react";
import { Controller, useForm } from "react-hook-form";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import {
  ManagerPickerField,
  type ManagerOption,
} from "@/modules/employees/components/ManagerPickerField";
import { useAllDepartmentsQuery } from "@/modules/employees/hooks/useDepartmentQueries";
import { EMPLOYMENT_TYPE_OPTIONS } from "@/modules/employees/types/employee.types";
import {
  employeeFormSchema,
  type EmployeeFormValues,
} from "@/modules/employees/validation/employeeSchema";

interface EmployeeFormProps {
  mode: "create" | "edit";
  defaultValues?: Partial<EmployeeFormValues>;
  employeeIdToExclude?: string;
  /** Edit mode only — seeds the Manager picker's "selected" view without an extra fetch. */
  initialManagerName?: string | null;
  onSubmit: (values: EmployeeFormValues) => void;
  isSubmitting: boolean;
  submitError?: string | null;
}

/**
 * Shared Create/Edit form — EMPLOYEE_API.md documents identical request
 * shapes for `POST /employees/` and `PATCH /employees/{id}/` (create adds
 * `user_id`, edit adds `last_working_date`), so one component with a `mode`
 * prop avoids duplicating every field twice. Department is a `<Select>` fed
 * by `useAllDepartmentsQuery` (see that hook's docstring for the
 * page_size:100 scope boundary). Manager is a search-as-you-type
 * `ManagerPickerField` (Phase 13 review requirement #4) — a flat dropdown of
 * every employee doesn't scale to a real organization's headcount.
 */
export function EmployeeForm({
  mode,
  defaultValues,
  employeeIdToExclude,
  initialManagerName,
  onSubmit,
  isSubmitting,
  submitError,
}: EmployeeFormProps) {
  const { data: departmentsPage } = useAllDepartmentsQuery();

  const {
    register,
    handleSubmit,
    control,
    formState: { errors },
  } = useForm<EmployeeFormValues>({
    resolver: zodResolver(employeeFormSchema),
    mode: "onTouched",
    defaultValues,
  });

  const [selectedManager, setSelectedManager] = useState<ManagerOption | null>(() =>
    defaultValues?.managerId
      ? {
          id: defaultValues.managerId,
          fullName: initialManagerName ?? "Current manager",
          employeeCode: null,
        }
      : null,
  );
  // Round 16 item 4 — an employee assigned as their own manager (e.g. a
  // CEO/Managing Director with no one to report to) routes leave approval
  // to themselves; see LeaveApprovalChainResolver's level-1 resolution,
  // which needs no change to support this — it just resolves `manager_id`
  // straight through. Only offered in edit mode: `employeeIdToExclude` (the
  // employee's own id) doesn't exist yet at create time, so this can only
  // be set after the employee record is created.
  const [isTopLevelManager, setIsTopLevelManager] = useState(
    () => Boolean(employeeIdToExclude) && defaultValues?.managerId === employeeIdToExclude,
  );

  const onValid = handleSubmit((values) => onSubmit(values));

  return (
    <form
      className="space-y-6"
      noValidate
      onSubmit={(event) => {
        void onValid(event);
      }}
    >
      {submitError ? (
        <div
          role="alert"
          className="rounded-md border border-destructive/50 bg-destructive/10 px-3 py-2 text-sm text-destructive"
        >
          {submitError}
        </div>
      ) : null}

      <div className="grid gap-4 sm:grid-cols-2">
        <div className="space-y-2">
          <Label htmlFor="firstName">First name</Label>
          <Input
            id="firstName"
            aria-invalid={Boolean(errors.firstName)}
            {...register("firstName")}
          />
          {errors.firstName ? (
            <p className="text-sm text-destructive">{errors.firstName.message}</p>
          ) : null}
        </div>
        <div className="space-y-2">
          <Label htmlFor="lastName">Last name</Label>
          <Input id="lastName" aria-invalid={Boolean(errors.lastName)} {...register("lastName")} />
          {errors.lastName ? (
            <p className="text-sm text-destructive">{errors.lastName.message}</p>
          ) : null}
        </div>

        <div className="space-y-2">
          <Label htmlFor="workEmail">Work email</Label>
          <Input
            id="workEmail"
            type="email"
            aria-invalid={Boolean(errors.workEmail)}
            {...register("workEmail")}
          />
          {errors.workEmail ? (
            <p className="text-sm text-destructive">{errors.workEmail.message}</p>
          ) : null}
        </div>
        <div className="space-y-2">
          <Label htmlFor="personalEmail">Personal email (optional)</Label>
          <Input id="personalEmail" type="email" {...register("personalEmail")} />
          {errors.personalEmail ? (
            <p className="text-sm text-destructive">{errors.personalEmail.message}</p>
          ) : null}
        </div>

        <div className="space-y-2">
          <Label htmlFor="phoneNumber">Phone number (optional)</Label>
          <Input id="phoneNumber" {...register("phoneNumber")} />
        </div>
        <div className="space-y-2">
          <Label htmlFor="dateOfBirth">Date of birth (optional)</Label>
          <Input id="dateOfBirth" type="date" {...register("dateOfBirth")} />
        </div>

        <div className="space-y-2">
          <Label htmlFor="gender">Gender (optional)</Label>
          <Input id="gender" {...register("gender")} />
        </div>

        <div className="space-y-2">
          <Label htmlFor="departmentId">Department</Label>
          <Controller
            control={control}
            name="departmentId"
            render={({ field }) => (
              <Select value={field.value} onValueChange={field.onChange}>
                <SelectTrigger id="departmentId" aria-invalid={Boolean(errors.departmentId)}>
                  <SelectValue placeholder="Select a department" />
                </SelectTrigger>
                <SelectContent>
                  {(departmentsPage?.items ?? []).map((department) => (
                    <SelectItem key={department.id} value={department.id}>
                      {department.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}
          />
          {errors.departmentId ? (
            <p className="text-sm text-destructive">{errors.departmentId.message}</p>
          ) : null}
        </div>

        <div className="space-y-2">
          <Label htmlFor="managerId">Manager (optional)</Label>
          <Controller
            control={control}
            name="managerId"
            render={({ field }) => (
              <div className="space-y-2">
                {employeeIdToExclude ? (
                  <div className="flex items-center justify-between rounded-md border border-border px-3 py-2">
                    <div>
                      <p className="text-sm font-medium text-foreground">Top-level (no manager)</p>
                      <p className="text-xs text-muted-foreground">
                        e.g. CEO/Managing Director — leave requests are routed to this employee for
                        their own approval instead of to someone else.
                      </p>
                    </div>
                    <Switch
                      aria-label="Mark as top-level (self-approving) manager"
                      checked={isTopLevelManager}
                      onCheckedChange={(checked) => {
                        setIsTopLevelManager(checked);
                        if (checked) {
                          setSelectedManager(null);
                          field.onChange(employeeIdToExclude);
                        } else {
                          field.onChange("");
                        }
                      }}
                    />
                  </div>
                ) : null}
                {!isTopLevelManager ? (
                  <ManagerPickerField
                    selected={selectedManager}
                    excludeEmployeeId={employeeIdToExclude}
                    onSelect={(manager) => {
                      setSelectedManager(manager);
                      field.onChange(manager?.id ?? "");
                    }}
                  />
                ) : null}
              </div>
            )}
          />
        </div>

        <div className="space-y-2">
          <Label htmlFor="jobTitle">Job title</Label>
          <Input id="jobTitle" aria-invalid={Boolean(errors.jobTitle)} {...register("jobTitle")} />
          {errors.jobTitle ? (
            <p className="text-sm text-destructive">{errors.jobTitle.message}</p>
          ) : null}
        </div>

        <div className="space-y-2">
          <Label htmlFor="employmentType">Employment type</Label>
          <Controller
            control={control}
            name="employmentType"
            render={({ field }) => (
              <Select value={field.value} onValueChange={field.onChange}>
                <SelectTrigger id="employmentType" aria-invalid={Boolean(errors.employmentType)}>
                  <SelectValue placeholder="Select a type" />
                </SelectTrigger>
                <SelectContent>
                  {EMPLOYMENT_TYPE_OPTIONS.map((option) => (
                    <SelectItem key={option.value} value={option.value}>
                      {option.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}
          />
          {errors.employmentType ? (
            <p className="text-sm text-destructive">{errors.employmentType.message}</p>
          ) : null}
        </div>

        <div className="space-y-2">
          <Label htmlFor="dateOfJoining">Date of joining</Label>
          <Input
            id="dateOfJoining"
            type="date"
            aria-invalid={Boolean(errors.dateOfJoining)}
            {...register("dateOfJoining")}
          />
          {errors.dateOfJoining ? (
            <p className="text-sm text-destructive">{errors.dateOfJoining.message}</p>
          ) : null}
        </div>

        {mode === "edit" ? (
          <div className="space-y-2">
            <Label htmlFor="lastWorkingDate">Last working date (optional)</Label>
            <Input id="lastWorkingDate" type="date" {...register("lastWorkingDate")} />
          </div>
        ) : null}
      </div>

      <div className="flex justify-end gap-2">
        <Button type="submit" disabled={isSubmitting}>
          {isSubmitting ? (
            <>
              <Loader2 className="size-4 animate-spin" aria-hidden="true" />
              Saving...
            </>
          ) : mode === "create" ? (
            "Create employee"
          ) : (
            "Save changes"
          )}
        </Button>
      </div>
    </form>
  );
}
