import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { LeaveBalance } from "@/modules/leave/types/leave.types";

interface LeaveBalanceCardsProps {
  balances: LeaveBalance[];
}

/** View Leave Balance — one card per active leave type, the entry point
 * every Leave Dashboard visit starts with. */
export function LeaveBalanceCards({ balances }: LeaveBalanceCardsProps) {
  if (balances.length === 0) {
    return <p className="text-sm text-muted-foreground">No leave balance data yet.</p>;
  }

  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {balances.map((balance) => (
        <Card key={balance.leaveTypeId}>
          <CardHeader className="pb-2">
            <CardTitle className="text-base">{balance.leaveTypeName ?? "Leave"}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-1">
            <p className="text-2xl font-semibold text-foreground">
              {balance.availableDays}
              <span className="ml-1 text-sm font-normal text-muted-foreground">days available</span>
            </p>
            <div className="grid grid-cols-2 gap-x-4 gap-y-1 pt-2 text-xs text-muted-foreground">
              <span>Entitled: {balance.entitledDays}</span>
              <span>Used: {balance.usedDays}</span>
              <span>Carried forward: {balance.carriedForwardDays}</span>
              <span>Pending: {balance.pendingDays}</span>
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
