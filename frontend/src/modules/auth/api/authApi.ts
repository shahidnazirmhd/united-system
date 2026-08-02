import { API_ENDPOINTS } from "@/lib/api/endpoints";
import { httpClient } from "@/lib/api/httpClient";
import type { ApiSuccessResponse } from "@/lib/api/types";
import type { AuthTokenPairResponse, LoginCredentials } from "@/modules/auth/types/auth.types";

/** The exact wire shape IDENTITY_API.md documents for `POST /auth/login/`. */
interface TokenPairWireResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

/**
 * POST /api/v1/auth/login/ — exchanges email + password for a token pair.
 * Error responses (`401 invalid_credentials` / `401 inactive_user`) are
 * already normalized into `ApiError` by httpClient's response interceptor
 * before they reach this function's caller — there is nothing to catch or
 * translate here.
 */
export async function login(credentials: LoginCredentials): Promise<AuthTokenPairResponse> {
  const response = await httpClient.post<ApiSuccessResponse<TokenPairWireResponse>>(
    `${API_ENDPOINTS.auth}/login/`,
    credentials,
  );
  const { access_token, refresh_token, token_type, expires_in } = response.data.data;
  return {
    accessToken: access_token,
    refreshToken: refresh_token,
    tokenType: token_type,
    expiresIn: expires_in,
  };
}
