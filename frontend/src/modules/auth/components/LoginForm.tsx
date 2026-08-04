import { zodResolver } from "@hookform/resolvers/zod";
import { Loader2 } from "lucide-react";
import { useForm } from "react-hook-form";

import { PasswordInput } from "@/components/common/PasswordInput";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ApiError } from "@/lib/api/types";
import { useLoginMutation } from "@/modules/auth/hooks/useLoginMutation";
import { loginSchema, type LoginFormValues } from "@/modules/auth/validation/loginSchema";

// Backend error codes this screen knows how to phrase in plain language —
// see IDENTITY_API.md's error table. Anything else falls back to the
// ApiError's own message, and a non-ApiError falls back to a generic string.
const ERROR_MESSAGES_BY_CODE: Record<string, string> = {
  invalid_credentials: "Incorrect email or password.",
  inactive_user: "This account has been deactivated. Contact your administrator.",
  network_error: "Unable to reach the server. Check your connection and try again.",
  session_expired: "Your session has expired. Please sign in again.",
};

function describeLoginError(error: unknown): string {
  if (error instanceof ApiError) {
    return ERROR_MESSAGES_BY_CODE[error.code] ?? error.message;
  }
  return "Something went wrong. Please try again.";
}

/**
 * The real login form, replacing Phase 10's inert `LoginPlaceholderPage`.
 * Renders inside `AuthLayout` via `LoginPage`. Field validation is
 * react-hook-form + zod (`loginSchema`); submission is `useLoginMutation`,
 * which owns talking to the backend and updating session state on success.
 */
export function LoginForm() {
  const mutation = useLoginMutation();
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<LoginFormValues>({
    resolver: zodResolver(loginSchema),
    mode: "onTouched",
  });

  const onSubmit = handleSubmit((values) => {
    mutation.mutate(values);
  });

  return (
    <form
      className="space-y-6"
      noValidate
      onSubmit={(event) => {
        void onSubmit(event);
      }}
    >
      <div className="space-y-1 text-center">
        <h1 className="text-xl font-semibold text-foreground">Sign in</h1>
        <p className="text-sm text-muted-foreground">
          Enter your credentials to access your account.
        </p>
      </div>

      {mutation.isError ? (
        <div
          role="alert"
          className="rounded-md border border-destructive/50 bg-destructive/10 px-3 py-2 text-sm text-destructive"
        >
          {describeLoginError(mutation.error)}
        </div>
      ) : null}

      <div className="space-y-4">
        <div className="space-y-2">
          <Label htmlFor="email">Email</Label>
          <Input
            id="email"
            type="email"
            placeholder="you@example.com"
            autoComplete="username"
            disabled={mutation.isPending}
            aria-invalid={Boolean(errors.email)}
            {...register("email")}
          />
          {errors.email ? <p className="text-sm text-destructive">{errors.email.message}</p> : null}
        </div>

        <div className="space-y-2">
          <Label htmlFor="password">Password</Label>
          <PasswordInput
            id="password"
            placeholder="••••••••"
            autoComplete="current-password"
            disabled={mutation.isPending}
            aria-invalid={Boolean(errors.password)}
            {...register("password")}
          />
          {errors.password ? (
            <p className="text-sm text-destructive">{errors.password.message}</p>
          ) : null}
        </div>

        <Button type="submit" className="w-full" disabled={mutation.isPending}>
          {mutation.isPending ? (
            <>
              <Loader2 className="size-4 animate-spin" aria-hidden="true" />
              Signing in...
            </>
          ) : (
            "Sign in"
          )}
        </Button>
      </div>
    </form>
  );
}
