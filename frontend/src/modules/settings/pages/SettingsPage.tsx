import { Loader2 } from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";

import { ErrorState, PageHeader, PageLoader } from "@/components/common";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useHasPermission } from "@/lib/auth/usePermission";
import { useUpdateSettingMutation } from "@/modules/settings/hooks/useSettingsMutations";
import { useSettingsQuery } from "@/modules/settings/hooks/useSettingsQueries";
import { DEFAULT_WEEK_OFF_KEY, WEEKDAY_OPTIONS } from "@/modules/settings/types/setting.types";

/**
 * Application Settings — a flat, generic key-value screen (round 14 item
 * 4). Only "Default Week Off" exists today; future settings are meant to be
 * added to this same page without restructuring, per the generic
 * key-value backend design (apps.settings) this page reads from.
 */
export function SettingsPage() {
  const canManage = useHasPermission("settings.manage_settings");
  const { data, isLoading, isError, refetch } = useSettingsQuery();
  const updateMutation = useUpdateSettingMutation();

  const [weekOff, setWeekOff] = useState<number | null>(null);

  const weekOffSetting = data?.find((setting) => setting.key === DEFAULT_WEEK_OFF_KEY);

  useEffect(() => {
    if (typeof weekOffSetting?.value === "number") {
      setWeekOff(weekOffSetting.value);
    }
  }, [weekOffSetting]);

  const handleWeekOffChange = (value: string) => {
    const numericValue = Number(value);
    setWeekOff(numericValue);
    updateMutation.mutate(
      { key: DEFAULT_WEEK_OFF_KEY, value: numericValue },
      {
        onSuccess: () => toast.success("Default week off was updated."),
        onError: (error) => {
          toast.error(error.message);
          if (typeof weekOffSetting?.value === "number") {
            setWeekOff(weekOffSetting.value);
          }
        },
      },
    );
  };

  return (
    <div>
      <PageHeader title="Settings" description="Application-wide settings. More will be added here over time." />

      {isLoading ? (
        <PageLoader label="Loading settings…" />
      ) : isError ? (
        <ErrorState
          title="Couldn't load settings"
          onRetry={() => {
            void refetch();
          }}
        />
      ) : (
        <div className="max-w-md rounded-lg border border-border p-4">
          <div className="space-y-2">
            <Label htmlFor="default-week-off">Default Week Off</Label>
            <Select
              value={weekOff !== null ? String(weekOff) : undefined}
              onValueChange={handleWeekOffChange}
              disabled={!canManage || updateMutation.isPending}
            >
              <SelectTrigger id="default-week-off">
                <SelectValue placeholder="Select a day" />
              </SelectTrigger>
              <SelectContent>
                {WEEKDAY_OPTIONS.map((option) => (
                  <SelectItem key={option.value} value={String(option.value)}>
                    {option.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <p className="text-sm text-muted-foreground">
              Used across the organization to exclude the weekly off day from leave working-day
              calculations.
            </p>
          </div>
          {updateMutation.isPending ? (
            <div className="mt-3 flex items-center gap-2 text-sm text-muted-foreground">
              <Loader2 className="size-4 animate-spin" aria-hidden="true" />
              Saving...
            </div>
          ) : null}
          {!canManage ? (
            <p className="mt-3 text-sm text-muted-foreground">
              You have read-only access to settings.
            </p>
          ) : null}
        </div>
      )}
    </div>
  );
}
