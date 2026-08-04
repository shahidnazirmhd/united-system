import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import {
  CHART_AXIS_TICK,
  CHART_GRID_STROKE,
  CHART_TOOLTIP_STYLE,
} from "@/modules/dashboard/components/chartTheme";
import type { ChartDatum } from "@/modules/dashboard/types/dashboard.types";

interface CategoryBarChartProps {
  data: ChartDatum[];
  height?: number;
  color?: string;
}

/**
 * Generic Bar chart — accepts any `{name, value}[]` breakdown. Backs
 * Department Statistics today; a future "requests by status" or "headcount
 * by job title" widget reuses this component unchanged, matching
 * `DonutChart`'s identical "one component, many datasets" reasoning.
 */
export function CategoryBarChart({
  data,
  height = 240,
  color = "hsl(var(--primary))",
}: CategoryBarChartProps) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} margin={{ top: 4, right: 8, left: -16, bottom: 4 }}>
        <CartesianGrid strokeDasharray="3 3" stroke={CHART_GRID_STROKE} vertical={false} />
        <XAxis dataKey="name" tick={CHART_AXIS_TICK} axisLine={false} tickLine={false} />
        <YAxis
          allowDecimals={false}
          tick={CHART_AXIS_TICK}
          axisLine={false}
          tickLine={false}
          width={32}
        />
        <Tooltip cursor={{ fill: "hsl(var(--muted))" }} contentStyle={CHART_TOOLTIP_STYLE} />
        <Bar dataKey="value" fill={color} radius={[4, 4, 0, 0]} maxBarSize={48} />
      </BarChart>
    </ResponsiveContainer>
  );
}
