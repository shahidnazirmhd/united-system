import { z } from "zod";

/**
 * Client-side shape validation only — mirrors what the backend's
 * `LoginSerializer` requires structurally (a well-formed email, a
 * non-empty password), not the business rule of whether those credentials
 * are actually correct. That check only ever happens server-side and comes
 * back as an `invalid_credentials`/`inactive_user` ApiError, which
 * `LoginForm` surfaces separately from these field-level errors.
 */
export const loginSchema = z.object({
  email: z.string().min(1, "Email is required").email("Enter a valid email address"),
  password: z.string().min(1, "Password is required"),
});

export type LoginFormValues = z.infer<typeof loginSchema>;
