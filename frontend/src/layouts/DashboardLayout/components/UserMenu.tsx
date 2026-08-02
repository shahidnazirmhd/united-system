import { LogOut, Settings, User } from "lucide-react";

import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useCurrentUserQuery, useSignOut } from "@/lib/auth";

function initialsFromEmail(email: string): string {
  return email.charAt(0).toUpperCase() || "U";
}

/**
 * Account menu. "Sign out" is wired to the real session-termination flow as
 * of Phase 11 (`useSignOut` — revokes the refresh token server-side,
 * clears local session state, and lets `ProtectedRoute` react to that on
 * its own). As of Phase 12, the header/label show the real signed-in user
 * via `useCurrentUserQuery` (`GET /auth/me/`) instead of a static
 * placeholder — falls back to "Signed-in user" while the query is loading
 * or if it errors, rather than blocking the menu on that request. Settings
 * stays disabled: no settings screen exists yet.
 */
export function UserMenu() {
  const signOut = useSignOut();
  const { data: currentUser } = useCurrentUserQuery();

  const displayName = currentUser?.email ?? "Signed-in user";
  const roleNames = currentUser?.roles.map((role) => role.name).join(", ");

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" className="relative size-9 rounded-full" aria-label="Account menu">
          <Avatar className="size-9">
            <AvatarFallback>
              {currentUser ? initialsFromEmail(currentUser.email) : "U"}
            </AvatarFallback>
          </Avatar>
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-56">
        <DropdownMenuLabel className="font-normal">
          <div className="flex flex-col space-y-1">
            <p className="truncate text-sm font-medium leading-none">{displayName}</p>
            <p className="truncate text-xs leading-none text-muted-foreground">
              {roleNames || "No roles assigned"}
            </p>
          </div>
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuItem disabled>
          <User className="mr-2 size-4" aria-hidden="true" />
          Profile
        </DropdownMenuItem>
        <DropdownMenuItem disabled>
          <Settings className="mr-2 size-4" aria-hidden="true" />
          Settings
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuItem
          onClick={() => {
            void signOut();
          }}
        >
          <LogOut className="mr-2 size-4" aria-hidden="true" />
          Sign out
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
