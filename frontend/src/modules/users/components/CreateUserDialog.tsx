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
import { EmployeePickerField } from "@/modules/users/components/EmployeePickerField";
import { RoleCheckboxList } from "@/modules/users/components/RoleCheckboxList";
import { useCreateUserWithAssignmentsMutation } from "@/modules/users/hooks/useUserMutations";
import { useRolesQuery } from "@/modules/users/hooks/useRoleQueries";
import type { LinkableEmployee } from "@/modules/users/api/userApi";
import {
  createUserFormSchema,
  type CreateUserFormValues,
} from "@/modules/users/validation/userSchema";

interface CreateUserDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

/**
 * Create User (Phase 12; extended in the Role & Permission Management
 * phase): `POST /api/v1/auth/users/`, then optionally links the chosen
 * employee and assigns the chosen roles — see
 * `useCreateUserWithAssignmentsMutation`'s docstring for why those two
 * steps are separate backend calls composed here rather than one bigger
 * endpoint.
 */
export function CreateUserDialog({ open, onOpenChange }: CreateUserDialogProps) {
  const mutation = useCreateUserWithAssignmentsMutation();
  const { data: roles, isLoading: isLoadingRoles } = useRolesQuery();
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [selectedEmployee, setSelectedEmployee] = useState<LinkableEmployee | null>(null);
  const [selectedRoleIds, setSelectedRoleIds] = useState<string[]>([]);

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<CreateUserFormValues>({
    resolver: zodResolver(createUserFormSchema),
    mode: "onTouched",
    defaultValues: { email: "", password: "" },
  });

  useEffect(() => {
    if (open) {
      reset({ email: "", password: "" });
      setSubmitError(null);
      setSelectedEmployee(null);
      setSelectedRoleIds([]);
    }
  }, [open, reset]);

  const onValid = handleSubmit((values) => {
    setSubmitError(null);
    mutation.mutate(
      { ...values, employeeId: selectedEmployee?.id ?? null, roleIds: selectedRoleIds },
      {
        onSuccess: (user) => {
          toast.success(`${user.email} was created.`);
          onOpenChange(false);
        },
        onError: (error) => {
          if (error.code === "duplicate_email") {
            setSubmitError("A user with this email already exists.");
          } else {
            setSubmitError(error.message);
          }
        },
      },
    );
  });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>New user</DialogTitle>
          <DialogDescription>
            Provisions a new authentication account. This is not the same as creating an employee
            record. You can optionally link an existing employee and assign roles now, or do either
            later.
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
            <Label htmlFor="new-user-email">Email</Label>
            <Input
              id="new-user-email"
              type="email"
              aria-invalid={Boolean(errors.email)}
              {...register("email")}
            />
            {errors.email ? (
              <p className="text-sm text-destructive">{errors.email.message}</p>
            ) : null}
          </div>

          <div className="space-y-2">
            <Label htmlFor="new-user-password">Password</Label>
            <Input
              id="new-user-password"
              type="password"
              autoComplete="new-password"
              aria-invalid={Boolean(errors.password)}
              {...register("password")}
            />
            {errors.password ? (
              <p className="text-sm text-destructive">{errors.password.message}</p>
            ) : null}
          </div>

          <div className="space-y-2">
            <Label>Link to employee (optional)</Label>
            <EmployeePickerField selected={selectedEmployee} onSelect={setSelectedEmployee} />
          </div>

          <div className="space-y-2">
            <Label>Roles (optional)</Label>
            <RoleCheckboxList
              roles={roles ?? []}
              isLoading={isLoadingRoles}
              selectedRoleIds={selectedRoleIds}
              onChange={setSelectedRoleIds}
            />
          </div>

          <DialogFooter>
            <Button type="submit" disabled={mutation.isPending}>
              {mutation.isPending ? (
                <>
                  <Loader2 className="size-4 animate-spin" aria-hidden="true" />
                  Creating...
                </>
              ) : (
                "Create user"
              )}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
