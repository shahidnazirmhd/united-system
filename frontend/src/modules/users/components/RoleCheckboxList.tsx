import { Checkbox } from "@/components/ui/checkbox";
import type { Role } from "@/modules/users/types/role.types";

interface RoleCheckboxListProps {
  roles: Role[];
  isLoading?: boolean;
  selectedRoleIds: string[];
  onChange: (roleIds: string[]) => void;
}

/**
 * The role multi-select shared by `CreateUserDialog` and `EditUserDialog` —
 * both need "assign one or more roles" and neither's field set is large
 * enough to justify two separate implementations. Deliberately a plain
 * checkbox list, not a searchable combobox: the role catalogue is the same
 * small, rarely-changing set `RoleFormDialog`'s permission picker already
 * assumes (see `usePermissionsQuery`'s docstring for the identical call).
 */
export function RoleCheckboxList({ roles, isLoading, selectedRoleIds, onChange }: RoleCheckboxListProps) {
  if (isLoading) {
    return <p className="text-sm text-muted-foreground">Loading roles…</p>;
  }

  if (roles.length === 0) {
    return <p className="text-sm text-muted-foreground">No roles exist yet.</p>;
  }

  return (
    <div className="max-h-48 space-y-1.5 overflow-y-auto rounded-md border border-border p-3">
      {roles.map((role) => {
        const checked = selectedRoleIds.includes(role.id);
        return (
          <label key={role.id} className="flex cursor-pointer items-start gap-2 py-0.5 text-sm">
            <Checkbox
              checked={checked}
              onChange={(event) => {
                onChange(
                  event.target.checked
                    ? [...selectedRoleIds, role.id]
                    : selectedRoleIds.filter((id) => id !== role.id),
                );
              }}
            />
            <span>
              <span className="font-medium text-foreground">{role.name}</span>
              {role.description ? (
                <span className="block text-xs text-muted-foreground">{role.description}</span>
              ) : null}
            </span>
          </label>
        );
      })}
    </div>
  );
}
