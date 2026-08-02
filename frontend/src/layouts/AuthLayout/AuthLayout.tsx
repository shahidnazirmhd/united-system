import { Outlet } from "react-router-dom";

import { Logo } from "@/components/common/Logo";
import { ThemeToggle } from "@/components/common/ThemeToggle";

/**
 * Centered-card shell for unauthenticated flows (login, password reset, OTP
 * verification, ...). No authentication logic lives here — this is
 * presentation only. `src/modules/auth`'s real `LoginPage` (Phase 11)
 * renders inside it via `<Outlet />`; a future password-reset/OTP page
 * would render the same way.
 */
export function AuthLayout() {
  return (
    <div className="relative flex min-h-screen items-center justify-center bg-muted/40 px-4 py-12">
      <div className="absolute right-4 top-4">
        <ThemeToggle />
      </div>
      <div className="w-full max-w-md space-y-8">
        <div className="flex justify-center">
          <Logo />
        </div>
        <div className="rounded-lg border border-border bg-card p-8 shadow-sm">
          <Outlet />
        </div>
      </div>
    </div>
  );
}
