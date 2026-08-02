import { useState } from "react";
import { Area, AreaChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { Button } from "@/components/ui/button";
import { CHART_AXIS_TICK, CHART_GRID_STROKE, CHART_TOOLTIP_STYLE } from "@/modules/dashboard/components/chartTheme";
import type { LeaveMonthlyStat } from "@/modules/dashboard/types/dashboard.types";

type TrendView = "area" | "line";

interface LeaveTrendChartProps {
  data: LeaveMonthlyStat[];
  height?: number;
}

function formatMonthLabel(month: string): string {
  const [year, monthNumber] = month.split("-").map(Number);
  if (!year || !monthNumber) return month;
  return new Date(year, monthNumber - 1, 1).toLocaleDateString(undefined, { month: "short" });
}

/**
 * Leave applications monthly trend, with a Line/Area view toggle over the
 * exact same series — a deliberate design choice (see the Phase 14
 * implementation notes) rather than fabricating a second, unrelated time
 * series just to have "one of each" chart type: this is the only true
 * time-series data the Dashboard's backend exposes
 * (`LeaveStatistics.monthlyTrend`, already zero-filled for gap-free months
 * — see the backend's `LeaveRequestService.get_statistics` docstring), so
 * both required chart types render it honestly instead of inventing data.
 */
export function LeaveTrendChart({ data, height = 220 }: LeaveTrendChartProps) {
  const [view, setView] = useState<TrendView>("area");
  const chartData = data.map((point) => ({ month: formatMonthLabel(point.month), count: point.count }));

  return (
    <div>
      <div className="mb-2 flex justify-end gap-1">
        <Button
          type="button"
          variant={view === "line" ? "secondary" : "ghost"}
          size="sm"
          className="h-7 px-2 text-xs"
          onClick={() => setView("line")}
        >
          Line
        </Button>
        <Button
          type="button"
          variant={view === "area" ? "secondary" : "ghost"}
          size="sm"
          className="h-7 px-2 text-xs"
          onClick={() => setView("area")}
        >
          Area
        </Button>
      </div>
      <ResponsiveContainer width="100%" height={height}>
        {view === "area" ? (
          <AreaChart data={chartData} margin={{ top: 4, right: 8, left: -16, bottom: 4 }}>
            <defs>
              <linearGradient id="leaveTrendFill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="hsl(var(--primary))" stopOpacity={0.35} />
                <stop offset="95%" stopColor="hsl(var(--primary))" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke={CHART_GRID_STROKE} vertical={false} />
            <XAxis dataKey="month" tick={CHART_AXIS_TICK} axisLine={false} tickLine={false} />
            <YAxis allowDecimals={false} tick={CHART_AXIS_TICK} axisLine={false} tickLine={false} width={32} />
            <Tooltip contentStyle={CHART_TOOLTIP_STYLE} />
            <Area
              type="monotone"
              dataKey="count"
              name="Applications"
              stroke="hsl(var(--primary))"
              fill="url(#leaveTrendFill)"
              strokeWidth={2}
            />
          </AreaChart>
        ) : (
          <LineChart data={chartData} margin={{ top: 4, right: 8, left: -16, bottom: 4 }}>
            <CartesianGrid strokeDasharray="3 3" stroke={CHART_GRID_STROKE} vertical={false} />
            <XAxis dataKey="month" tick={CHART_AXIS_TICK} axisLine={false} tickLine={false} />
            <YAxis allowDecimals={false} tick={CHART_AXIS_TICK} axisLine={false} tickLine={false} width={32} />
            <Tooltip contentStyle={CHART_TOOLTIP_STYLE} />
            <Line
              type="monotone"
              dataKey="count"
              name="Applications"
              stroke="hsl(var(--primary))"
              strokeWidth={2}
              dot={{ r: 3 }}
            />
          </LineChart>
        )}
      </ResponsiveContainer>
    </div>
  );
}
