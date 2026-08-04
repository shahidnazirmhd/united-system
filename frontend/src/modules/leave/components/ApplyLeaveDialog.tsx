import { zodResolver } from "@hookform/resolvers/zod";
import { AlertTriangle, Loader2 } from "lucide-react";
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { LeaveEmployeePickerField } from "@/modules/leave/components/LeaveEmployeePickerField";
import { useLevel1ApprovalCheckQuery } from "@/modules/leave/hooks/useLeaveQueries";
import {
  LEVEL1_SKIP_REASON_LABELS,
  type LeaveEmployeeOption,
  type LeaveType,
} from "@/modules/leave/types/leave.types";
import {
  applyLeaveFormSchema,
  type ApplyLeaveFormValues,
} from "@/modules/leave/validation/applyLeaveSchema";

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
  // HR Leave Workflow round, item 1 — set only when this HR-on-behalf
  // application's Level 1 approval will be skipped and the user hasn't yet
  // confirmed submission. Holding the validated form values here (rather
  // than immediately submitting) lets the confirmation step re-use the
  // exact same values the user already filled in once they confirm.
  const [pendingSubmission, setPendingSubmission] = useState<ApplyLeaveFormValues | null>(null);

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
      setPendingSubmission(null);
    }
  }, [open, reset]);

  // Only meaningful for the HR-on-behalf flow — self-service apply never
  // renders the employee picker at all, so this stays disabled (no
  // employeeId) for that case.
  const level1Check = useLevel1ApprovalCheckQuery(
    allowEmployeeSelection ? (selectedEmployee?.id ?? undefined) : undefined,
  );
  const willSkipLevel1 = allowEmployeeSelection && (level1Check.data?.willSkipLevel1 ?? false);
  const skipReasonLabel = level1Check.data?.skipReason
    ? (LEVEL1_SKIP_REASON_LABELS[level1Check.data.skipReason] ?? level1Check.data.skipReason)
    : null;

  const onValid = handleSubmit((values) => {
    if (willSkipLevel1) {
      // Requirement: show a confirmation dialog explaining the skip before
      // submitting — handled by swapping the form for a confirmation panel
      // below (see the `pendingSubmission` render branch), rather than a
      // second nested Dialog.
      setPendingSubmission(values);
      return;
    }
    onSubmit(values, selectedEmployee);
  });

  const handleConfirmSkipAndSubmit = () => {
    if (pendingSubmission) {
      onSubmit(pendingSubmission, selectedEmployee);
      // Reset immediately rather than waiting for the mutation to settle —
      // if it fails, `submitError` renders over the ordinary form again
      // (below), which is where the user expects to see it and retry from.
      setPendingSubmission(null);
    }
  };

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

        {pendingSubmission ? (
          // HR Leave Workflow round, item 1 — the required pre-submit
          // confirmation step, shown in place of the form once the user has
          // submitted valid values for an employee whose Level 1 approval
          // will be skipped. Explains why, and requires an explicit second
          // action before anything is actually sent.
          <div className="space-y-4">
            <div
              role="alert"
              className="flex items-start gap-2 rounded-md border border-amber-500/50 bg-amber-500/10 px-3 py-2 text-sm text-amber-900 dark:text-amber-200"
            >
              <AlertTriangle className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
              <span>
                Level 1 (manager) approval will be skipped for this request
                {skipReasonLabel ? ` — ${skipReasonLabel}` : ""}. It will go directly to Level 2
                (HR/Admin) approval instead.
              </span>
            </div>
            <DialogFooter>
              <Button type="button" variant="ghost" onClick={() => setPendingSubmission(null)}>
                Go back
              </Button>
              <Button type="button" disabled={isSubmitting} onClick={handleConfirmSkipAndSubmit}>
                {isSubmitting ? (
                  <Loader2 className="size-4 animate-spin" aria-hidden="true" />
                ) : null}
                Confirm &amp; submit
              </Button>
            </DialogFooter>
          </div>
        ) : (
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
                <LeaveEmployeePickerField
                  selected={selectedEmployee}
                  onSelect={setSelectedEmployee}
                />
                {willSkipLevel1 ? (
                  <p className="flex items-start gap-1.5 text-xs text-amber-700 dark:text-amber-400">
                    <AlertTriangle className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
                    <span>
                      Level 1 approval will be skipped for this employee
                      {skipReasonLabel ? ` (${skipReasonLabel})` : ""}.
                    </span>
                  </p>
                ) : null}
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
              {errors.leaveTypeId ? (
                <p className="text-sm text-destructive">{errors.leaveTypeId.message}</p>
              ) : null}
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
                {errors.startDate ? (
                  <p className="text-sm text-destructive">{errors.startDate.message}</p>
                ) : null}
              </div>
              <div className="space-y-2">
                <Label htmlFor="apply-end-date">End date</Label>
                <Input
                  id="apply-end-date"
                  type="date"
                  aria-invalid={Boolean(errors.endDate)}
                  {...register("endDate")}
                />
                {errors.endDate ? (
                  <p className="text-sm text-destructive">{errors.endDate.message}</p>
                ) : null}
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="apply-reason">Reason (optional)</Label>
              <Textarea id="apply-reason" {...register("reason")} />
            </div>

            <DialogFooter>
              <Button type="submit" disabled={isSubmitting}>
                {isSubmitting ? (
                  <Loader2 className="size-4 animate-spin" aria-hidden="true" />
                ) : null}
                Apply for leave
              </Button>
            </DialogFooter>
          </form>
        )}
      </DialogContent>
    </Dialog>
  );
}
