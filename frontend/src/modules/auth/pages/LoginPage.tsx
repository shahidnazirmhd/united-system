import { LoginForm } from "@/modules/auth/components/LoginForm";

/**
 * Route-level page for `/auth/login`, replacing Phase 10's
 * `LoginPlaceholderPage`. Kept deliberately thin — all real behavior lives
 * in `LoginForm`; this file exists only so the router has a page-shaped
 * export to lazy-load, per the convention in `app/router/withSuspense.tsx`.
 */
export function LoginPage() {
  return <LoginForm />;
}
