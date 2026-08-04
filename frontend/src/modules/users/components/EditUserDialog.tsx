import { zodResolver } from "@hookform/resolvers/zod";
import { Loader2 } from "lucide-react";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";

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
import { ApiError } from "@/lib/api/types";
import { EmployeePickerField } from "@/modules/users/components/EmployeePickerField";
import { RoleCheckboxList } from "@/modules/users/components/RoleCheckboxList";
import { useRolesQuery } from "@/modules/users/hooks/useRoleQueries";
import {
  useLinkUserToEmployeeMutation,
  useSyncUserRolesMutation,
  useUpdateUserMutation,
} from "@/modules/users/hooks/useUserMutations";
import type { LinkableEmployee } from "@/modules/users/api/userApi";
import type { ManagedUser } from "@/modules/users/types/user.types";
import {
  updateUserFormSchema,
  type UpdateUserFormValues,
} from "@/modules/users/validation/userSchema";

interface EditUserDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  user: ManagedUser | undefined;
}

/**
 * Edit User (Phase 12; extended in the Role & Permission Management phase):
 * `PATCH /api/v1/auth/users/{id}/` for email, plus — new this phase —
 * optionally linking an employee (only offered while `user.employeeId` is
 * still null; there is no unlink endpoint, so once linked this dialog has
 * nothing further to do there) and syncing role assignments via
 * `useSyncUserRolesMutation`'s add/revoke diff. Password, is_active, and
 * (once linked) the employee link stay on their own dedicated actions —
 * exactly as IDENTITY_API.md documents. The "System Account" toggle that
 * used to live here was removed after investigation found
 * `is_system_account` had no functional effect anywhere in the backend —
 * see IDENTITY_API.md's migration note (0005_remove_is_system_account).
 */
export function EditUserDialog({ open, onOpenChange, user }: EditUserDialogProps) {
  const updateMutation = useUpdateUserMutation();
  const linkMutation = useLinkUserToEmployeeMutation();
  const syncRolesMutation = useSyncUserRolesMutation();
  const { data: roles, isLoading: isLoadingRoles } = useRolesQuery();

  const [submitError, setSubmitError] = useState<string | null>(null);
  const [selectedEmployee, setSelectedEmployee] = useState<LinkableEmployee | null>(null);
  const [selectedRoleIds, setSelectedRoleIds] = useState<string[]>([]);

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<UpdateUserFormValues>({
    resolver: zodResolver(updateUserFormSchema),
    mode: "onTouched",
    defaultValues: { email: "" },
  });

  useEffect(() => {
    if (open && user) {
      reset({ email: user.email });
      setSubmitError(null);
      setSelectedEmployee(null);
      setSelectedRoleIds(user.roles.map((role) => role.id));
    }
  }, [open, user, reset]);

  const isSubmitting =
    updateMutation.isPending || linkMutation.isPending || syncRolesMutation.isPending;

  const onValid = handleSubmit(async (values) => {
    if (!user) return;
    setSubmitError(null);

    const currentRoleIds = user.roles.map((role) => role.id);
    const addRoleIds = selectedRoleIds.filter((id) => !currentRoleIds.includes(id));
    const removeRoleIds = currentRoleIds.filter((id) => !selectedRoleIds.includes(id));

    // Sequential, not Promise.all, and awaited directly (mutateAsync) rather
    // than nesting an async onSuccess callback (which @typescript-eslint/
    // no-misused-promises correctly rejects — a void-returning callback slot
    // shouldn't silently swallow a rejected promise): email update surfaces
    // the more likely validation error (duplicate_email) first, before
    // committing any employee-link/role-sync side effects.
    try {
      const updated = await updateMutation.mutateAsync({ userId: user.id, input: values });
      if (selectedEmployee) {
        await linkMutation.mutateAsync({ employeeId: selectedEmployee.id, userId: user.id });
      }
      if (addRoleIds.length > 0 || removeRoleIds.length > 0) {
        await syncRolesMutation.mutateAsync({ userId: user.id, addRoleIds, removeRoleIds });
      }
      toast.success(`${updated.email} was updated.`);
      onOpenChange(false);
    } catch (error) {
      if (error instanceof ApiError && error.code === "duplicate_email") {
        setSubmitError("Another user already has this email.");
      } else if (error instanceof Error) {
        setSubmitError(error.message);
      } else {
        setSubmitError("Some changes could not be saved.");
      }
    }
  });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Edit user</DialogTitle>
          <DialogDescription>
            Updates this account's email, employee link, and roles.
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
            <Label htmlFor="edit-user-email">Email</Label>
            <Input
              id="edit-user-email"
              type="email"
              aria-invalid={Boolean(errors.email)}
              {...register("email")}
            />
            {errors.email ? (
              <p className="text-sm text-destructive">{errors.email.message}</p>
            ) : null}
          </div>

          <div className="space-y-2">
            <Label>Linked employee</Label>
            {user?.employeeId ? (
              <div className="rounded-md border border-border px-3 py-2 text-sm text-muted-foreground">
                Already linked to an employee record.
              </div>
            ) : (
              <EmployeePickerField selected={selectedEmployee} onSelect={setSelectedEmployee} />
            )}
          </div>

          <div className="space-y-2">
            <Label>Roles</Label>
            <RoleCheckboxList
              roles={roles ?? []}
              isLoading={isLoadingRoles}
              selectedRoleIds={selectedRoleIds}
              onChange={setSelectedRoleIds}
            />
          </div>

          <DialogFooter>
            <Button type="submit" disabled={isSubmitting}>
              {isSubmitting ? (
                <>
                  <Loader2 className="size-4 animate-spin" aria-hidden="true" />
                  Saving...
                </>
              ) : (
                "Save changes"
              )}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
