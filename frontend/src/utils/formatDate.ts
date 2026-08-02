/**
 * Centralized date formatting so every future module renders dates
 * consistently (e.g. a Leave request's start/end date and an Approval's
 * decided_at should look the same everywhere) instead of each screen
 * hand-rolling its own `Intl.DateTimeFormat` call.
 */
export function formatDate(date: string | Date, options?: Intl.DateTimeFormatOptions): string {
  const parsed = typeof date === "string" ? new Date(date) : date;
  return new Intl.DateTimeFormat(
    "en-US",
    options ?? { year: "numeric", month: "short", day: "2-digit" },
  ).format(parsed);
}

export function formatDateTime(date: string | Date): string {
  const parsed = typeof date === "string" ? new Date(date) : date;
  return new Intl.DateTimeFormat("en-US", { dateStyle: "medium", timeStyle: "short" }).format(
    parsed,
  );
}

export function formatRelativeToNow(date: string | Date): string {
  const parsed = typeof date === "string" ? new Date(date) : date;
  const diffMs = parsed.getTime() - Date.now();
  const diffMinutes = Math.round(diffMs / (1000 * 60));

  const formatter = new Intl.RelativeTimeFormat("en-US", { numeric: "auto" });

  if (Math.abs(diffMinutes) < 60) return formatter.format(diffMinutes, "minute");
  const diffHours = Math.round(diffMinutes / 60);
  if (Math.abs(diffHours) < 24) return formatter.format(diffHours, "hour");
  const diffDays = Math.round(diffHours / 24);
  return formatter.format(diffDays, "day");
}
