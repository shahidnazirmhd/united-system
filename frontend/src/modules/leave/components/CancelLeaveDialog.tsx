import { Loader2 } from "lucide-react";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import type { LeaveRequest } from "@/modules/leave/types/leave.types";

interface CancelLeaveDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  leaveRequest?: LeaveRequest;
  onConfirm: (cancellationReason: string | null) => void;
  isSubmitting: boolean;
  submitError?: string | null;
}

export function CancelLeaveDialog({
  open,
  onOpenChange,
  leaveRequest,
  onConfirm,
  isSubmitting,
  submitError,
}: CancelLeaveDialogProps) {
  const [reason, setReason] = useState("");

  useEffect(() => {
    if (open) {
      setReason("");
    }
  }, [open]);

  if (!leaveRequest) {
    return null;
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Cancel leave request</DialogTitle>
          <DialogDescription>
            {leaveRequest.leaveTypeName ?? "Leave"}: {leaveRequest.startDate} → {leaveRequest.endDate}.{" "}
            {leaveRequest.status === "approved"
              ? "This request is already approved — cancelling will restore the balance it consumed."
              : "This request is still pending — cancelling will also close its approval process; " +
                "the approver will no longer be able to act on it."}
          </DialogDescription>
        </DialogHeader>

        {submitError ? (
          <div
            role="alert"
            className="rounded-md border border-destructive/50 bg-destructive/10 px-3 py-2 text-sm text-destructive"
          >
            {submitError}
          </div>
        ) : null}

        <div className="space-y-2">
          <Label htmlFor="cancel-reason">Reason (optional)</Label>
          <Textarea
            id="cancel-reason"
            value={reason}
            onChange={(event) => setReason(event.target.value)}
            placeholder="No longer needed…"
          />
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={isSubmitting}>
            Keep request
          </Button>
          <Button variant="destructive" disabled={isSubmitting} onClick={() => onConfirm(reason.trim() || null)}>
            {isSubmitting ? <Loader2 className="size-4 animate-spin" aria-hidden="true" /> : null}
            Cancel leave
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
