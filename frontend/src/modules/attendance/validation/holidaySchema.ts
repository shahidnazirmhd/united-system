import { z } from "zod";

/** Client-side shape validation only — see departmentSchema.ts's identical caveat. */
export const holidayFormSchema = z.object({
  name: z.string().trim().min(1, "Name is required").max(150),
  holidayDate: z.string().trim().min(1, "Date is required"),
  description: z.string().trim().max(1000).optional().default(""),
  isActive: z.boolean().default(true),
});

export type HolidayFormValues = z.infer<typeof holidayFormSchema>;
