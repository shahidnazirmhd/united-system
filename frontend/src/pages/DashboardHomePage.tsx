import { CalendarClock, ClipboardCheck, Clock, Users } from "lucide-react";

import { PageHeader } from "@/components/common/PageHeader";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

const SUMMARY_CARDS = [
  { label: "Employees", icon: Users },
  { label: "Pending Leave Requests", icon: CalendarClock },
  { label: "Pending Approvals", icon: ClipboardCheck },
  { label: "Open Attendance Items", icon: Clock },
] as const;

/**
 * The dashboard's index route (`/`). Lazy-loaded from app/router/routes.tsx
 * as a worked example of the route-based code-splitting convention — real
 * summary data will replace these static cards once the modules that back
 * them (Employees, Leave, Approvals, Attendance) are built.
 */
export function DashboardHomePage() {
  return (
    <div>
      <PageHeader
        title="Dashboard"
        description="An overview will appear here once the underlying modules are built."
      />
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {SUMMARY_CARDS.map((card) => (
          <Card key={card.label}>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">
                {card.label}
              </CardTitle>
              <card.icon className="size-4 text-muted-foreground" aria-hidden="true" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-semibold text-foreground">—</div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
