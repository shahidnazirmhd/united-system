import { z } from "zod";

/** Client-side shape validation only — see `modules/auth/validation/loginSchema.ts`'s docstring. */
export const createUserFormSchema = z.object({
  email: z.string().trim().min(1, "Email is required").email("Enter a valid email address"),
  password: z
    .string()
    .min(10, "Password must be at least 10 characters")
    .max(128, "Password is too long"),
});
export type CreateUserFormValues = z.infer<typeof createUserFormSchema>;

export const updateUserFormSchema = z.object({
  email: z.string().trim().min(1, "Email is required").email("Enter a valid email address"),
});
export type UpdateUserFormValues = z.infer<typeof updateUserFormSchema>;
