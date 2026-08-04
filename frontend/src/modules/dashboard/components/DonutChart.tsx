import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";

import { CHART_COLORS, CHART_TOOLTIP_STYLE } from "@/modules/dashboard/components/chartTheme";
import type { ChartDatum } from "@/modules/dashboard/types/dashboard.types";

interface DonutChartProps {
  data: ChartDatum[];
  height?: number;
}

/**
 * Generic Pie/Donut chart — accepts any `{name, value}[]` breakdown, so the
 * same component backs both the Employee Statistics section's Employment
 * Type donut and the Leave Statistics section's Leave Type donut (see
 * `dashboard.types.ts`'s `ChartDatum` docstring). A custom legend list is
 * rendered below the chart (rather than recharts' own `<Legend>`) so its
 * colors/typography match the rest of this app's design system exactly.
 */
export function DonutChart({ data, height = 200 }: DonutChartProps) {
  const total = data.reduce((sum, point) => sum + point.value, 0);

  return (
    <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
      <ResponsiveContainer width="100%" height={height} className="sm:max-w-[180px]">
        <PieChart>
          <Pie
            data={data}
            dataKey="value"
            nameKey="name"
            innerRadius="58%"
            outerRadius="85%"
            paddingAngle={data.length > 1 ? 2 : 0}
            stroke="none"
          >
            {data.map((entry, index) => (
              <Cell key={entry.name} fill={CHART_COLORS[index % CHART_COLORS.length]} />
            ))}
          </Pie>
          <Tooltip
            contentStyle={CHART_TOOLTIP_STYLE}
            formatter={(value: number) => [value, "Count"]}
          />
        </PieChart>
      </ResponsiveContainer>
      <ul className="flex-1 space-y-1.5">
        {data.map((point, index) => (
          <li key={point.name} className="flex items-center justify-between gap-2 text-xs">
            <span className="flex items-center gap-2 text-muted-foreground">
              <span
                className="size-2.5 shrink-0 rounded-full"
                style={{ backgroundColor: CHART_COLORS[index % CHART_COLORS.length] }}
                aria-hidden="true"
              />
              {point.name}
            </span>
            <span className="font-medium text-foreground">
              {point.value}
              <span className="ml-1 text-muted-foreground">
                ({total > 0 ? Math.round((point.value / total) * 100) : 0}%)
              </span>
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
