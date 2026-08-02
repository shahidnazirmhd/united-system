import { z } from "zod";

/** Client-side shape validation only — `duplicate_leave_type_code` only
 * ever comes back as an `ApiError`. */
export const leaveTypeFormSchema = z.object({
  name: z.string().trim().min(1, "Name is required").max(50),
  code: z
    .string()
    .trim()
    .min(1, "Code is required")
    .max(20)
    .transform((value) => value.toUpperCase()),
  defaultAnnualDays: z
    .string()
    .trim()
    .min(1, "Default annual days is required")
    .refine((value) => !Number.isNaN(Number(value)) && Number(value) >= 0, {
      message: "Enter a non-negative number",
    }),
  isPaid: z.boolean().default(true),
  requiresApproval: z.boolean().default(true),
  isActive: z.boolean().default(true),
});

export type LeaveTypeFormValues = z.infer<typeof leaveTypeFormSchema>;
