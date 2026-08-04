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
import {
  LEAVE_TYPE_STATUS_MAPPING_OPTIONS,
  type LeaveType,
} from "@/modules/leave/types/leave.types";
import {
  leaveTypeFormSchema,
  type LeaveTypeFormValues,
} from "@/modules/leave/validation/leaveTypeSchema";

interface LeaveTypeFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  leaveType?: LeaveType;
  onSubmit: (values: LeaveTypeFormValues) => void;
  isSubmitting: boolean;
  submitError?: string | null;
}

/** One dialog handles both Create and Edit — Leave Type's field set is
 * small, same judgment call `DepartmentFormDialog` already made. */
export function LeaveTypeFormDialog({
  open,
  onOpenChange,
  leaveType,
  onSubmit,
  isSubmitting,
  submitError,
}: LeaveTypeFormDialogProps) {
  const {
    register,
    handleSubmit,
    control,
    reset,
    formState: { errors },
  } = useForm<LeaveTypeFormValues>({
    resolver: zodResolver(leaveTypeFormSchema),
    mode: "onTouched",
    defaultValues: {
      name: "",
      code: "",
      defaultAnnualDays: "0",
      isPaid: true,
      requiresApproval: true,
      isActive: true,
      mapsToEmployeeStatus: "none",
    },
  });

  useEffect(() => {
    if (open) {
      reset({
        name: leaveType?.name ?? "",
        code: leaveType?.code ?? "",
        defaultAnnualDays: leaveType?.defaultAnnualDays ?? "0",
        isPaid: leaveType?.isPaid ?? true,
        requiresApproval: leaveType?.requiresApproval ?? true,
        isActive: leaveType?.isActive ?? true,
        mapsToEmployeeStatus: leaveType?.mapsToEmployeeStatus ?? "none",
      });
    }
  }, [open, leaveType, reset]);

  const onValid = handleSubmit((values) => onSubmit(values));

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{leaveType ? "Edit leave type" : "New leave type"}</DialogTitle>
          <DialogDescription>
            {leaveType ? "Update this leave type's details." : "Creates a new leave type."}
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
            <Label htmlFor="leave-type-name">Name</Label>
            <Input id="leave-type-name" aria-invalid={Boolean(errors.name)} {...register("name")} />
            {errors.name ? <p className="text-sm text-destructive">{errors.name.message}</p> : null}
          </div>

          <div className="space-y-2">
            <Label htmlFor="leave-type-code">Code</Label>
            <Input id="leave-type-code" aria-invalid={Boolean(errors.code)} {...register("code")} />
            {errors.code ? <p className="text-sm text-destructive">{errors.code.message}</p> : null}
          </div>

          <div className="space-y-2">
            <Label htmlFor="leave-type-default-days">Default annual days</Label>
            <Input
              id="leave-type-default-days"
              aria-invalid={Boolean(errors.defaultAnnualDays)}
              {...register("defaultAnnualDays")}
            />
            {errors.defaultAnnualDays ? (
              <p className="text-sm text-destructive">{errors.defaultAnnualDays.message}</p>
            ) : null}
          </div>

          <div className="space-y-2">
            <Label htmlFor="leave-type-status-mapping">Drives Employee Current Status</Label>
            <Controller
              control={control}
              name="mapsToEmployeeStatus"
              render={({ field }) => (
                <Select value={field.value} onValueChange={field.onChange}>
                  <SelectTrigger id="leave-type-status-mapping">
                    <SelectValue placeholder="None" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="none">None</SelectItem>
                    {LEAVE_TYPE_STATUS_MAPPING_OPTIONS.map((option) => (
                      <SelectItem key={option.value} value={option.value}>
                        {option.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}
            />
            <p className="text-xs text-muted-foreground">
              When set, an employee&apos;s Current Status automatically switches to this value while
              an approved request of this leave type is in progress, and reverts when it ends. Leave
              as &quot;None&quot; for leave types that shouldn&apos;t affect Current Status.
            </p>
          </div>

          <div className="flex items-center justify-between rounded-md border border-border px-3 py-2">
            <Label htmlFor="leave-type-paid">Paid</Label>
            <Controller
              control={control}
              name="isPaid"
              render={({ field }) => (
                <Switch
                  id="leave-type-paid"
                  checked={field.value}
                  onCheckedChange={field.onChange}
                />
              )}
            />
          </div>

          <div className="flex items-center justify-between rounded-md border border-border px-3 py-2">
            <Label htmlFor="leave-type-requires-approval">Requires approval</Label>
            <Controller
              control={control}
              name="requiresApproval"
              render={({ field }) => (
                <Switch
                  id="leave-type-requires-approval"
                  checked={field.value}
                  onCheckedChange={field.onChange}
                />
              )}
            />
          </div>

          {leaveType ? (
            <div className="flex items-center justify-between rounded-md border border-border px-3 py-2">
              <Label htmlFor="leave-type-active">Active</Label>
              <Controller
                control={control}
                name="isActive"
                render={({ field }) => (
                  <Switch
                    id="leave-type-active"
                    checked={field.value}
                    onCheckedChange={field.onChange}
                  />
                )}
              />
            </div>
          ) : null}

          <DialogFooter>
            <Button type="submit" disabled={isSubmitting}>
              {isSubmitting ? <Loader2 className="size-4 animate-spin" aria-hidden="true" /> : null}
              {leaveType ? "Save changes" : "Create leave type"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
