/** Mirrors the backend's generic key-value `SettingResponseSerializer`. */
export interface Setting {
  key: string;
  value: unknown;
  description: string;
}

/** 0=Monday ... 6=Sunday, matching the backend's `_validate_week_off` convention. */
export const WEEKDAY_OPTIONS = [
  { value: 0, label: "Monday" },
  { value: 1, label: "Tuesday" },
  { value: 2, label: "Wednesday" },
  { value: 3, label: "Thursday" },
  { value: 4, label: "Friday" },
  { value: 5, label: "Saturday" },
  { value: 6, label: "Sunday" },
] as const;

export const DEFAULT_WEEK_OFF_KEY = "default_week_off";
