import { z } from "zod";

const nonNegativeDecimalString = z
  .string()
  .trim()
  .min(1, "Required")
  .refine((value) => !Number.isNaN(Number(value)) && Number(value) >= 0, {
    message: "Enter a non-negative number",
  });

/** Backs both Leave Balance Opening and Adjustment dialogs — same shape,
 * different copy/defaults at the component level (see
 * BalanceAdjustmentDialog.tsx). `invalid_leave_balance_adjustment` (a
 * negative value slipping past this client-side check) only ever comes
 * back as an `ApiError`. */
export const balanceAdjustmentFormSchema = z.object({
  employeeId: z.string().trim().min(1, "Employee is required"),
  leaveTypeId: z.string().trim().min(1, "Leave type is required"),
  year: z
    .string()
    .trim()
    .min(1, "Year is required")
    .refine((value) => Number.isInteger(Number(value)), { message: "Enter a valid year" }),
  entitledDays: nonNegativeDecimalString,
  usedDays: nonNegativeDecimalString,
  carriedForwardDays: nonNegativeDecimalString,
  reason: z.string().trim().min(1, "A reason is required for audit purposes").max(500),
});

export type BalanceAdjustmentFormValues = z.infer<typeof balanceAdjustmentFormSchema>;
