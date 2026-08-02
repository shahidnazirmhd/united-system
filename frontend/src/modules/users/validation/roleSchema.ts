import { z } from "zod";

/** Client-side shape validation only — see `userSchema.ts`'s docstring for the same caveat. */
export const roleFormSchema = z.object({
  name: z.string().trim().min(1, "Name is required").max(50),
  description: z.string().trim().max(500).optional().default(""),
  permissionCodes: z.array(z.string()).default([]),
});
export type RoleFormValues = z.infer<typeof roleFormSchema>;
