import { useMutation, type UseMutationResult } from "@tanstack/react-query";

import type { ApiError } from "@/lib/api/types";
import { useAuth } from "@/lib/auth";
import { login } from "@/modules/auth/api/authApi";
import type { AuthTokenPairResponse } from "@/modules/auth/types/auth.types";
import type { LoginFormValues } from "@/modules/auth/validation/loginSchema";

/**
 * Wraps the login API call in a TanStack Query mutation. On success, hands
 * the token pair to `useAuth().login()` so `AuthProvider`'s session state
 * (and every route guard reading it) updates in the same tick. Deliberately
 * no `navigate()` call here — see `app/router/PublicOnlyRoute.tsx` for why
 * the redirect to the dashboard happens on its own once `isAuthenticated`
 * flips to true.
 */
export function useLoginMutation(): UseMutationResult<
  AuthTokenPairResponse,
  ApiError,
  LoginFormValues
> {
  const { login: startSession } = useAuth();

  return useMutation({
    mutationFn: login,
    onSuccess: (tokens) => {
      startSession({ accessToken: tokens.accessToken, refreshToken: tokens.refreshToken });
    },
  });
}
