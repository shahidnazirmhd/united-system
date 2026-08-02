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
import {
  balanceAdjustmentFormSchema,
  type BalanceAdjustmentFormValues,
} from "@/modules/leave/validation/balanceAdjustmentSchema";

interface BalanceAdjustmentDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  mode: "open" | "adjust";
  leaveTypes: LeaveType[];
  onSubmit: (values: BalanceAdjustmentFormValues, employee: LeaveEmployeeOption | null) => void;
  isSubmitting: boolean;
  submitError?: string | null;
}

/**
 * One dialog, one backend call (`POST /leave/balances/adjust/`), two named
 * Phase 13 features: "Leave Balance Opening" (`mode="open"` — copy and
 * defaults assume no row exists yet for the picked employee/type/year) and
 * "Leave Balance Adjustment" (`mode="adjust"` — copy assumes an existing
 * row is being corrected). The backend itself decides which actually
 * happened (creates vs. updates) and reports it back as `adjustment_type`
 * in the response — this dialog's `mode` only changes what's shown to the
 * user before submitting, never what's sent.
 */
export function BalanceAdjustmentDialog({
  open,
  onOpenChange,
  mode,
  leaveTypes,
  onSubmit,
  isSubmitting,
  submitError,
}: BalanceAdjustmentDialogProps) {
  const [selectedEmployee, setSelectedEmployee] = useState<LeaveEmployeeOption | null>(null);
  const currentYear = new Date().getFullYear();

  const {
    register,
    handleSubmit,
    control,
    reset,
    formState: { errors },
  } = useForm<BalanceAdjustmentFormValues>({
    resolver: zodResolver(balanceAdjustmentFormSchema),
    mode: "onTouched",
    defaultValues: {
      employeeId: "",
      leaveTypeId: "",
      year: String(mode === "open" ? currentYear + 1 : currentYear),
      entitledDays: "0",
      usedDays: "0",
      carriedForwardDays: "0",
      reason: "",
    },
  });

  useEffect(() => {
    if (open) {
      reset({
        employeeId: "",
        leaveTypeId: "",
        year: String(mode === "open" ? currentYear + 1 : currentYear),
        entitledDays: "0",
        usedDays: "0",
        carriedForwardDays: "0",
        reason: "",
      });
      setSelectedEmployee(null);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, mode, reset]);

  const onValid = handleSubmit((values) => onSubmit(values, selectedEmployee));

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{mode === "open" ? "Open a leave balance" : "Adjust a leave balance"}</DialogTitle>
          <DialogDescription>
            {mode === "open"
              ? "Creates a fresh entitlement for an employee/leave type/year that has no balance row yet."
              : "Overwrites an existing balance row's values. Always recorded to the audit trail."}
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
            <Label>Employee</Label>
            <input type="hidden" {...register("employeeId")} value={selectedEmployee?.id ?? ""} readOnly />
            <LeaveEmployeePickerField
              selected={selectedEmployee}
              onSelect={(employee) => {
                setSelectedEmployee(employee);
              }}
            />
            {errors.employeeId ? <p className="text-sm text-destructive">{errors.employeeId.message}</p> : null}
          </div>

          <div className="space-y-2">
            <Label htmlFor="balance-leave-type">Leave type</Label>
            <Controller
              control={control}
              name="leaveTypeId"
              render={({ field }) => (
                <Select value={field.value} onValueChange={field.onChange}>
                  <SelectTrigger id="balance-leave-type" aria-invalid={Boolean(errors.leaveTypeId)}>
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

          <div className="space-y-2">
            <Label htmlFor="balance-year">Year</Label>
            <Input id="balance-year" aria-invalid={Boolean(errors.year)} {...register("year")} />
            {errors.year ? <p className="text-sm text-destructive">{errors.year.message}</p> : null}
          </div>

          <div className="grid grid-cols-3 gap-4">
            <div className="space-y-2">
              <Label htmlFor="balance-entitled">Entitled days</Label>
              <Input id="balance-entitled" aria-invalid={Boolean(errors.entitledDays)} {...register("entitledDays")} />
              {errors.entitledDays ? (
                <p className="text-sm text-destructive">{errors.entitledDays.message}</p>
              ) : null}
            </div>
            <div className="space-y-2">
              <Label htmlFor="balance-used">Used days</Label>
              <Input id="balance-used" aria-invalid={Boolean(errors.usedDays)} {...register("usedDays")} />
              {errors.usedDays ? <p className="text-sm text-destructive">{errors.usedDays.message}</p> : null}
            </div>
            <div className="space-y-2">
              <Label htmlFor="balance-carried">Carried forward</Label>
              <Input
                id="balance-carried"
                aria-invalid={Boolean(errors.carriedForwardDays)}
                {...register("carriedForwardDays")}
              />
              {errors.carriedForwardDays ? (
                <p className="text-sm text-destructive">{errors.carriedForwardDays.message}</p>
              ) : null}
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor="balance-reason">Reason</Label>
            <Textarea
              id="balance-reason"
              aria-invalid={Boolean(errors.reason)}
              placeholder="Required for the audit trail…"
              {...register("reason")}
            />
            {errors.reason ? <p className="text-sm text-destructive">{errors.reason.message}</p> : null}
          </div>

          <DialogFooter>
            <Button type="submit" disabled={isSubmitting}>
              {isSubmitting ? <Loader2 className="size-4 animate-spin" aria-hidden="true" /> : null}
              {mode === "open" ? "Open balance" : "Save adjustment"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
