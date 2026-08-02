/**
 * Role & Permission Management. Mirrors IDENTITY_API.md's `RoleSerializer`/
 * `PermissionSerializer`, camelCased — same convention as this module's own
 * `user.types.ts`. Lives in `modules/users`, not a standalone `modules/roles`
 * — Role Management is a sub-view of User Management (reached via the Users
 * list page's header action), exactly mirroring how Department is a
 * sub-view of `modules/employees`, not its own module.
 */
export interface Role {
  id: string;
  name: string;
  description: string;
  isSystemRole: boolean;
  permissionCodes: string[];
}

export interface Permission {
  id: string;
  code: string;
  description: string;
  module: string;
}

export interface RoleFormInput {
  name: string;
  description: string;
  permissionCodes: string[];
}
