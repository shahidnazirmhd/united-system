import { zodResolver } from "@hookform/resolvers/zod";
import { Loader2 } from "lucide-react";
import { useEffect } from "react";
import { Controller, useForm } from "react-hook-form";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
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
import { useAllEmployeesQuery } from "@/modules/employees/hooks/useEmployeeQueries";
import { useAllDepartmentsQuery } from "@/modules/employees/hooks/useDepartmentQueries";
import type { Department } from "@/modules/employees/types/department.types";
import {
  departmentFormSchema,
  type DepartmentFormValues,
} from "@/modules/employees/validation/departmentSchema";

const NONE_VALUE = "__none__";

interface DepartmentFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  department?: Department;
  onSubmit: (values: DepartmentFormValues) => void;
  isSubmitting: boolean;
  submitError?: string | null;
}

/**
 * One dialog handles both Create and Update — Department's field set is
 * small enough (name, code, parent, head, is_active) that a full page per
 * action would be more scaffolding than the feature warrants, unlike
 * Employee's larger form. `department` present means edit mode.
 */
export function DepartmentFormDialog({
  open,
  onOpenChange,
  department,
  onSubmit,
  isSubmitting,
  submitError,
}: DepartmentFormDialogProps) {
  const { data: departmentsPage } = useAllDepartmentsQuery();
  const { data: employeesPage } = useAllEmployeesQuery();

  const {
    register,
    handleSubmit,
    control,
    reset,
    formState: { errors },
  } = useForm<DepartmentFormValues>({
    resolver: zodResolver(departmentFormSchema),
    mode: "onTouched",
    defaultValues: {
      name: "",
      code: "",
      parentDepartmentId: "",
      headEmployeeId: "",
      isActive: true,
    },
  });

  useEffect(() => {
    if (open) {
      reset({
        name: department?.name ?? "",
        code: department?.code ?? "",
        parentDepartmentId: department?.parentDepartmentId ?? "",
        headEmployeeId: department?.headEmployeeId ?? "",
        isActive: department?.isActive ?? true,
      });
    }
  }, [open, department, reset]);

  const parentOptions = (departmentsPage?.items ?? []).filter((d) => d.id !== department?.id);

  const onValid = handleSubmit((values) => onSubmit(values));

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{department ? "Edit department" : "New department"}</DialogTitle>
          <DialogDescription>
            {department ? "Update this department's details." : "Creates a new department."}
          </DialogDescription>
        </DialogHeader>

        <form
          className="space-y-4"
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

          <div className="space-y-2">
            <Label htmlFor="dept-name">Name</Label>
            <Input id="dept-name" aria-invalid={Boolean(errors.name)} {...register("name")} />
            {errors.name ? <p className="text-sm text-destructive">{errors.name.message}</p> : null}
          </div>

          <div className="space-y-2">
            <Label htmlFor="dept-code">Code</Label>
            <Input id="dept-code" aria-invalid={Boolean(errors.code)} {...register("code")} />
            {errors.code ? <p className="text-sm text-destructive">{errors.code.message}</p> : null}
          </div>

          <div className="space-y-2">
            <Label htmlFor="dept-parent">Parent department (optional)</Label>
            <Controller
              control={control}
              name="parentDepartmentId"
              render={({ field }) => (
                <Select
                  value={field.value || NONE_VALUE}
                  onValueChange={(value) => field.onChange(value === NONE_VALUE ? "" : value)}
                >
                  <SelectTrigger id="dept-parent">
                    <SelectValue placeholder="No parent" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value={NONE_VALUE}>No parent</SelectItem>
                    {parentOptions.map((option) => (
                      <SelectItem key={option.id} value={option.id}>
                        {option.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="dept-head">Head of department (optional)</Label>
            <Controller
              control={control}
              name="headEmployeeId"
              render={({ field }) => (
                <Select
                  value={field.value || NONE_VALUE}
                  onValueChange={(value) => field.onChange(value === NONE_VALUE ? "" : value)}
                >
                  <SelectTrigger id="dept-head">
                    <SelectValue placeholder="No head assigned" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value={NONE_VALUE}>No head assigned</SelectItem>
                    {(employeesPage?.items ?? []).map((employee) => (
                      <SelectItem key={employee.id} value={employee.id}>
                        {employee.fullName}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}
            />
          </div>

          {department ? (
            <div className="flex items-center justify-between rounded-md border border-border px-3 py-2">
              <Label htmlFor="dept-active">Active</Label>
              <Controller
                control={control}
                name="isActive"
                render={({ field }) => (
                  <Switch id="dept-active" checked={field.value} onCheckedChange={field.onChange} />
                )}
              />
            </div>
          ) : null}

          <DialogFooter>
            <Button type="submit" disabled={isSubmitting}>
              {isSubmitting ? (
                <>
                  <Loader2 className="size-4 animate-spin" aria-hidden="true" />
                  Saving...
                </>
              ) : department ? (
                "Save changes"
              ) : (
                "Create department"
              )}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
