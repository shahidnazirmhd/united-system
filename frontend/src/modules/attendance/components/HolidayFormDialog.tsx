import { zodResolver } from "@hookform/resolvers/zod";
import { Loader2 } from "lucide-react";
import { useEffect } from "react";
import { Controller, useForm } from "react-hook-form";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import type { Holiday } from "@/modules/attendance/types/holiday.types";
import { holidayFormSchema, type HolidayFormValues } from "@/modules/attendance/validation/holidaySchema";

interface HolidayFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  holiday?: Holiday;
  onSubmit: (values: HolidayFormValues) => void;
  isSubmitting: boolean;
  submitError?: string | null;
}

/**
 * One dialog handles both Create and Update — Holiday's field set (name,
 * date, description, is_active) is small enough that a full page per action
 * would be more scaffolding than the feature warrants, mirroring
 * DepartmentFormDialog's precedent.
 */
export function HolidayFormDialog({
  open,
  onOpenChange,
  holiday,
  onSubmit,
  isSubmitting,
  submitError,
}: HolidayFormDialogProps) {
  const {
    register,
    handleSubmit,
    control,
    reset,
    formState: { errors },
  } = useForm<HolidayFormValues>({
    resolver: zodResolver(holidayFormSchema),
    mode: "onTouched",
    defaultValues: { name: "", holidayDate: "", description: "", isActive: true },
  });

  useEffect(() => {
    if (open) {
      reset({
        name: holiday?.name ?? "",
        holidayDate: holiday?.holidayDate ?? "",
        description: holiday?.description ?? "",
        isActive: holiday?.isActive ?? true,
      });
    }
  }, [open, holiday, reset]);

  const onValid = handleSubmit((values) => onSubmit(values));

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{holiday ? "Edit holiday" : "New holiday"}</DialogTitle>
          <DialogDescription>
            {holiday ? "Update this holiday's details." : "Define an upcoming holiday."}
          </DialogDescription>
        </DialogHeader>

        <form
          className="space-y-4"
          noValidate
          onSubmit={(event) => {
            void onValid(event);
          }}
        >
          {submitError ? (
            <div
              role="alert"
              className="rounded-md border border-destructive/50 bg-destructive/10 px-3 py-2 text-sm text-destructive"
            >
              {submitError}
            </div>
          ) : null}

          <div className="space-y-2">
            <Label htmlFor="holiday-name">Name</Label>
            <Input id="holiday-name" aria-invalid={Boolean(errors.name)} {...register("name")} />
            {errors.name ? <p className="text-sm text-destructive">{errors.name.message}</p> : null}
          </div>

          <div className="space-y-2">
            <Label htmlFor="holiday-date">Date</Label>
            <Input
              id="holiday-date"
              type="date"
              aria-invalid={Boolean(errors.holidayDate)}
              {...register("holidayDate")}
            />
            {errors.holidayDate ? (
              <p className="text-sm text-destructive">{errors.holidayDate.message}</p>
            ) : null}
          </div>

          <div className="space-y-2">
            <Label htmlFor="holiday-description">Description (optional)</Label>
            <Textarea id="holiday-description" rows={3} {...register("description")} />
          </div>

          {holiday ? (
            <div className="flex items-center justify-between rounded-md border border-border px-3 py-2">
              <Label htmlFor="holiday-active">Active</Label>
              <Controller
                control={control}
                name="isActive"
                render={({ field }) => (
                  <Switch id="holiday-active" checked={field.value} onCheckedChange={field.onChange} />
                )}
              />
            </div>
          ) : null}

          <DialogFooter>
            <Button type="submit" disabled={isSubmitting}>
              {isSubmitting ? (
                <>
                  <Loader2 className="size-4 animate-spin" aria-hidden="true" />
                  Saving...
                </>
              ) : holiday ? (
                "Save changes"
              ) : (
                "Create holiday"
              )}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
