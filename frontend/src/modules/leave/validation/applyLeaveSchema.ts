import { z } from "zod";

/** Client-side shape validation only — every real business rule (balance
 * sufficiency, overlap, duplicate, date-range order, manager availability)
 * only ever comes back as an `ApiError` from `LeaveValidationService`, same
 * caveat every other module's own form schema documents. */
export const applyLeaveFormSchema = z
  .object({
    leaveTypeId: z.string().trim().min(1, "Leave type is required"),
    startDate: z.string().trim().min(1, "Start date is required"),
    endDate: z.string().trim().min(1, "End date is required"),
    reason: z
      .string()
      .trim()
      .optional()
      .transform((value) => (value ? value : undefined)),
    employeeId: z
      .string()
      .trim()
      .optional()
      .transform((value) => (value ? value : undefined)),
  })
  .refine((values) => values.endDate >= values.startDate, {
    message: "End date must be on or after the start date",
    path: ["endDate"],
  });

export type ApplyLeaveFormValues = z.infer<typeof applyLeaveFormSchema>;

export const cancelLeaveFormSchema = z.object({
  cancellationReason: z
    .string()
    .trim()
    .optional()
    .transform((value) => (value ? value : undefined)),
});

export type CancelLeaveFormValues = z.infer<typeof cancelLeaveFormSchema>;
