import { zodResolver } from "@hookform/resolvers/zod";
import { Loader2 } from "lucide-react";
import { useEffect, useMemo } from "react";
import { Controller, useForm } from "react-hook-form";

import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
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
import { usePermissionsQuery } from "@/modules/users/hooks/useRoleQueries";
import type { Permission, Role } from "@/modules/users/types/role.types";
import { roleFormSchema, type RoleFormValues } from "@/modules/users/validation/roleSchema";

interface RoleFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  role?: Role;
  onSubmit: (values: RoleFormValues) => void;
  isSubmitting: boolean;
  submitError?: string | null;
}

/**
 * One dialog handles both Create and Update — same "small enough field set,
 * one shared dialog" call `DepartmentFormDialog.tsx` made for its own
 * resource. `role` present means edit mode. Permissions render grouped by
 * `module` (identity, employees, leave, approvals, ...) rather than a flat
 * list — the catalogue is Open/Closed (every module seeds its own codes, see
 * `list_permissions.py`), so grouping by the field that's always present is
 * the only grouping that scales as more modules add permissions, without
 * this dialog needing to know what those future modules are.
 */
export function RoleFormDialog({
  open,
  onOpenChange,
  role,
  onSubmit,
  isSubmitting,
  submitError,
}: RoleFormDialogProps) {
  const { data: permissions, isLoading: isLoadingPermissions } = usePermissionsQuery();

  const {
    register,
    handleSubmit,
    control,
    reset,
    formState: { errors },
  } = useForm<RoleFormValues>({
    resolver: zodResolver(roleFormSchema),
    mode: "onTouched",
    defaultValues: { name: "", description: "", permissionCodes: [] },
  });

  useEffect(() => {
    if (open) {
      reset({
        name: role?.name ?? "",
        description: role?.description ?? "",
        permissionCodes: role?.permissionCodes ?? [],
      });
    }
  }, [open, role, reset]);

  const permissionsByModule = useMemo(() => {
    const groups = new Map<string, Permission[]>();
    for (const permission of permissions ?? []) {
      const existing = groups.get(permission.module) ?? [];
      groups.set(permission.module, [...existing, permission]);
    }
    return Array.from(groups.entries()).sort(([a], [b]) => a.localeCompare(b));
  }, [permissions]);

  const onValid = handleSubmit((values) => onSubmit(values));

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>{role ? "Edit role" : "New role"}</DialogTitle>
          <DialogDescription>
            {role
              ? "Update this role's name, description, and granted permissions."
              : "Creates a new role that can be assigned to users."}
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

          {role?.isSystemRole ? (
            <div className="rounded-md border border-border bg-muted/50 px-3 py-2 text-sm text-muted-foreground">
              This is a built-in system role. It can be edited but not deleted.
            </div>
          ) : null}

          <div className="space-y-2">
            <Label htmlFor="role-name">Name</Label>
            <Input id="role-name" aria-invalid={Boolean(errors.name)} {...register("name")} />
            {errors.name ? <p className="text-sm text-destructive">{errors.name.message}</p> : null}
          </div>

          <div className="space-y-2">
            <Label htmlFor="role-description">Description (optional)</Label>
            <Input id="role-description" {...register("description")} />
          </div>

          <div className="space-y-2">
            <Label>Permissions</Label>
            {isLoadingPermissions ? (
              <p className="text-sm text-muted-foreground">Loading permissions…</p>
            ) : (
              <Controller
                control={control}
                name="permissionCodes"
                render={({ field }) => (
                  <div className="max-h-72 space-y-4 overflow-y-auto rounded-md border border-border p-3">
                    {permissionsByModule.map(([module, modulePermissions]) => (
                      <div key={module} className="space-y-1.5">
                        <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                          {module}
                        </p>
                        {modulePermissions.map((permission) => {
                          const checked = field.value.includes(permission.code);
                          return (
                            <label
                              key={permission.code}
                              className="flex cursor-pointer items-start gap-2 py-0.5 text-sm"
                            >
                              <Checkbox
                                checked={checked}
                                onChange={(event) => {
                                  field.onChange(
                                    event.target.checked
                                      ? [...field.value, permission.code]
                                      : field.value.filter((code) => code !== permission.code),
                                  );
                                }}
                              />
                              <span>
                                <span className="font-medium text-foreground">
                                  {permission.code}
                                </span>
                                {permission.description ? (
                                  <span className="block text-xs text-muted-foreground">
                                    {permission.description}
                                  </span>
                                ) : null}
                              </span>
                            </label>
                          );
                        })}
                      </div>
                    ))}
                  </div>
                )}
              />
            )}
          </div>

          <DialogFooter>
            <Button type="submit" disabled={isSubmitting}>
              {isSubmitting ? (
                <>
                  <Loader2 className="size-4 animate-spin" aria-hidden="true" />
                  Saving...
                </>
              ) : role ? (
                "Save changes"
              ) : (
                "Create role"
              )}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
