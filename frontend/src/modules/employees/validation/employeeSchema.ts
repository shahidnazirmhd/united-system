import { z } from "zod";

/**
 * Client-side shape validation only, same convention/caveat as
 * `modules/auth/validation/loginSchema.ts`'s docstring — business rules
 * (duplicate work email, unknown department, etc.) only ever come back as
 * an `ApiError` from the backend. Optional text fields use `""` as the form
 * control's empty value and are normalized to `null` before hitting the API
 * (see `EmployeeForm.tsx`), matching EMPLOYEE_API.md's nullable fields.
 */
const optionalText = z
  .string()
  .trim()
  .optional()
  .transform((value) => (value ? value : undefined));

export const employeeFormSchema = z.object({
  firstName: z.string().trim().min(1, "First name is required").max(100),
  lastName: z.string().trim().min(1, "Last name is required").max(100),
  dateOfBirth: optionalText,
  gender: optionalText,
  workEmail: z
    .string()
    .trim()
    .min(1, "Work email is required")
    .email("Enter a valid email address"),
  personalEmail: z
    .string()
    .trim()
    .optional()
    .transform((value) => (value ? value : undefined))
    .refine((value) => value === undefined || z.string().email().safeParse(value).success, {
      message: "Enter a valid email address",
    }),
  phoneNumber: optionalText,
  departmentId: z.string().trim().min(1, "Department is required"),
  managerId: optionalText,
  jobTitle: z.string().trim().min(1, "Job title is required").max(150),
  employmentType: z.enum(["full_time", "part_time", "contract", "intern"], {
    required_error: "Employment type is required",
  }),
  dateOfJoining: z.string().trim().min(1, "Date of joining is required"),
  lastWorkingDate: optionalText, // round 15 item 9 — renamed from terminationDate
});

export type EmployeeFormValues = z.infer<typeof employeeFormSchema>;
