import { z } from "zod";

/** Client-side shape validation only — see `employeeSchema.ts`'s docstring for the same caveat. */
export const departmentFormSchema = z.object({
  name: z.string().trim().min(1, "Name is required").max(150),
  code: z
    .string()
    .trim()
    .min(1, "Code is required")
    .max(20)
    .transform((value) => value.toUpperCase()),
  parentDepartmentId: z
    .string()
    .trim()
    .optional()
    .transform((value) => (value ? value : undefined)),
  headEmployeeId: z
    .string()
    .trim()
    .optional()
    .transform((value) => (value ? value : undefined)),
  isActive: z.boolean().default(true),
});

export type DepartmentFormValues = z.infer<typeof departmentFormSchema>;
