/**
 * Shared chart color palette and axis/tooltip styling for every recharts
 * component in this module — one file so a future theme change (or a
 * future widget's new chart) picks up the same look automatically instead
 * of each chart component hardcoding its own colors. Colors reference the
 * app's existing CSS custom properties (index.css) rather than hardcoded
 * hex values, so charts follow light/dark mode the same way every other
 * component already does.
 */
export const CHART_COLORS: readonly string[] = [
  "hsl(var(--primary))",
  "hsl(var(--success))",
  "hsl(var(--warning))",
  "hsl(var(--destructive))",
  "hsl(var(--secondary-foreground))",
  "hsl(var(--muted-foreground))",
];

export const CHART_GRID_STROKE = "hsl(var(--border))";
export const CHART_AXIS_TICK = { fontSize: 12, fill: "hsl(var(--muted-foreground))" } as const;
export const CHART_TOOLTIP_STYLE = {
  borderRadius: 8,
  borderColor: "hsl(var(--border))",
  background: "hsl(var(--card))",
  color: "hsl(var(--foreground))",
  fontSize: 12,
} as const;
