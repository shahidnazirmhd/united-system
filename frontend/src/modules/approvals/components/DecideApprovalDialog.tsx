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
import type { ApprovalDecision, ApprovalRequest } from "@/modules/approvals/types/approval.types";

interface DecideApprovalDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  approvalRequest?: ApprovalRequest;
  onDecide: (decision: ApprovalDecision, comments: string | null) => void;
  isSubmitting: boolean;
  submitError?: string | null;
}

/**
 * One dialog handles both Approve and Reject — a single optional comments
 * field, two submit buttons rather than a decision dropdown, since the
 * decision is almost always the reason someone opened this dialog in the
 * first place (matches how a real approval inbox reads: you already know
 * whether you're approving or rejecting before you click).
 */
export function DecideApprovalDialog({
  open,
  onOpenChange,
  approvalRequest,
  onDecide,
  isSubmitting,
  submitError,
}: DecideApprovalDialogProps) {
  const [comments, setComments] = useState("");

  useEffect(() => {
    if (open) {
      setComments("");
    }
  }, [open]);

  if (!approvalRequest) {
    return null;
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Decide approval request</DialogTitle>
          <DialogDescription>{approvalRequest.subjectSummary}</DialogDescription>
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
          <Label htmlFor="decide-comments">Comments (optional)</Label>
          <Textarea
            id="decide-comments"
            value={comments}
            onChange={(event) => setComments(event.target.value)}
            placeholder="Add a note for the requester…"
          />
        </div>

        <DialogFooter className="gap-2 sm:gap-2">
          <Button
            variant="destructive"
            disabled={isSubmitting}
            onClick={() => onDecide("reject", comments.trim() || null)}
          >
            {isSubmitting ? <Loader2 className="size-4 animate-spin" aria-hidden="true" /> : null}
            Reject
          </Button>
          <Button disabled={isSubmitting} onClick={() => onDecide("approve", comments.trim() || null)}>
            {isSubmitting ? <Loader2 className="size-4 animate-spin" aria-hidden="true" /> : null}
            Approve
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
