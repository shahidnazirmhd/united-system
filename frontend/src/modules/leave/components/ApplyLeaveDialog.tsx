import { zodResolver } from "@hookform/resolvers/zod";
import { Loader2 } from "lucide-react";
import { useEffect, useState } from "react";
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
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { LeaveEmployeePickerField } from "@/modules/leave/components/LeaveEmployeePickerField";
import type { LeaveEmployeeOption, LeaveType } from "@/modules/leave/types/leave.types";
import { applyLeaveFormSchema, type ApplyLeaveFormValues } from "@/modules/leave/validation/applyLeaveSchema";

interface ApplyLeaveDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  leaveTypes: LeaveType[];
  allowEmployeeSelection: boolean;
  onSubmit: (values: ApplyLeaveFormValues, employee: LeaveEmployeeOption | null) => void;
  isSubmitting: boolean;
  submitError?: string | null;
}

/**
 * Apply Leave — one dialog handles both self-service and HR/Admin
 * "apply on behalf of an employee" (Phase 13). `allowEmployeeSelection`
 * (gated by `leave.manage_leave` at the page level) toggles whether the
 * employee picker renders; leaving it unpicked means "myself," matching
 * `ApplyLeaveRequest.employee_id` defaulting to the caller on the backend's
 * self-service endpoint.
 */
export function ApplyLeaveDialog({
  open,
  onOpenChange,
  leaveTypes,
  allowEmployeeSelection,
  onSubmit,
  isSubmitting,
  submitError,
}: ApplyLeaveDialogProps) {
  const [selectedEmployee, setSelectedEmployee] = useState<LeaveEmployeeOption | null>(null);

  const {
    register,
    handleSubmit,
    control,
    reset,
    formState: { errors },
  } = useForm<ApplyLeaveFormValues>({
    resolver: zodResolver(applyLeaveFormSchema),
    mode: "onTouched",
    defaultValues: { leaveTypeId: "", startDate: "", endDate: "", reason: "" },
  });

  useEffect(() => {
    if (open) {
      reset({ leaveTypeId: "", startDate: "", endDate: "", reason: "" });
      setSelectedEmployee(null);
    }
  }, [open, reset]);

  const onValid = handleSubmit((values) => onSubmit(values, selectedEmployee));

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Apply for leave</DialogTitle>
          <DialogDescription>
            {allowEmployeeSelection
              ? "Applies on your own behalf, or on behalf of an employee you pick below."
              : "Applies on your own behalf."}
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

          {allowEmployeeSelection ? (
            <div className="space-y-2">
              <Label>Employee (optional — leave blank to apply for yourself)</Label>
              <LeaveEmployeePickerField selected={selectedEmployee} onSelect={setSelectedEmployee} />
            </div>
          ) : null}

          <div className="space-y-2">
            <Label htmlFor="apply-leave-type">Leave type</Label>
            <Controller
              control={control}
              name="leaveTypeId"
              render={({ field }) => (
                <Select value={field.value} onValueChange={field.onChange}>
                  <SelectTrigger id="apply-leave-type" aria-invalid={Boolean(errors.leaveTypeId)}>
                    <SelectValue placeholder="Select a leave type" />
                  </SelectTrigger>
                  <SelectContent>
                    {leaveTypes.map((leaveType) => (
                      <SelectItem key={leaveType.id} value={leaveType.id}>
                        {leaveType.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}
            />
            {errors.leaveTypeId ? <p className="text-sm text-destructive">{errors.leaveTypeId.message}</p> : null}
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="apply-start-date">Start date</Label>
              <Input
                id="apply-start-date"
                type="date"
                aria-invalid={Boolean(errors.startDate)}
                {...register("startDate")}
              />
              {errors.startDate ? <p className="text-sm text-destructive">{errors.startDate.message}</p> : null}
            </div>
            <div className="space-y-2">
              <Label htmlFor="apply-end-date">End date</Label>
              <Input
                id="apply-end-date"
                type="date"
                aria-invalid={Boolean(errors.endDate)}
                {...register("endDate")}
              />
              {errors.endDate ? <p className="text-sm text-destructive">{errors.endDate.message}</p> : null}
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor="apply-reason">Reason (optional)</Label>
            <Textarea id="apply-reason" {...register("reason")} />
          </div>

          <DialogFooter>
            <Button type="submit" disabled={isSubmitting}>
              {isSubmitting ? <Loader2 className="size-4 animate-spin" aria-hidden="true" /> : null}
              Apply for leave
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
