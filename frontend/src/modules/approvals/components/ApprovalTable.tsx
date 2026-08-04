import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { ApprovalStatusBadge } from "@/modules/approvals/components/ApprovalStatusBadge";
import type { ApprovalRequest } from "@/modules/approvals/types/approval.types";

interface ApprovalTableProps {
  approvalRequests: ApprovalRequest[];
  onDecide: (approvalRequest: ApprovalRequest) => void;
}

export function ApprovalTable({ approvalRequests, onDecide }: ApprovalTableProps) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Subject</TableHead>
          <TableHead>Level</TableHead>
          <TableHead>Status</TableHead>
          <TableHead className="text-right">Actions</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {approvalRequests.map((approvalRequest) => (
          <TableRow key={approvalRequest.id}>
            <TableCell className="max-w-md whitespace-normal">
              {approvalRequest.subjectSummary}
            </TableCell>
            <TableCell>{approvalRequest.currentLevel}</TableCell>
            <TableCell>
              <ApprovalStatusBadge status={approvalRequest.status} />
            </TableCell>
            <TableCell className="text-right">
              <Button size="sm" onClick={() => onDecide(approvalRequest)}>
                Decide
              </Button>
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
