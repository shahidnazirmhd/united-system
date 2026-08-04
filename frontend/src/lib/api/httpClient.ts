import axios, { type AxiosError, type AxiosRequestConfig } from "axios";

import { env } from "@/config/env";
import { clearTokenPair, getAccessToken, getRefreshToken, setTokenPair } from "@/lib/api/authToken";
import { ApiError, type ApiErrorResponse, type ApiSuccessResponse } from "@/lib/api/types";
import { emitSessionExpired } from "@/lib/auth/sessionEvents";

/**
 * The single axios instance every API call in the application must go
 * through — no feature module should ever call `axios` directly or
 * construct its own instance. Centralizing it here is what makes the
 * request-auth-header, token-refresh, and response-error-normalization
 * behavior below apply uniformly, with zero duplicated code, to every
 * future module.
 */
export const httpClient = axios.create({
  baseURL: env.apiBaseUrl,
  headers: {
    "Content-Type": "application/json",
  },
  timeout: 15_000,
});

httpClient.interceptors.request.use((config) => {
  const token = getAccessToken();
  if (token) {
    config.headers.set("Authorization", `Bearer ${token}`);
  }
  return config;
});

/**
 * A second, interceptor-free axios instance used only to call the token
 * refresh endpoint. It must never go through `httpClient`'s own response
 * interceptor below — that would let a failed refresh attempt trigger
 * another refresh attempt, recursing forever.
 */
const refreshClient = axios.create({ baseURL: env.apiBaseUrl, timeout: 15_000 });

interface RefreshedTokenPair {
  access_token: string;
  refresh_token: string;
}

// Endpoints that must never trigger a refresh-and-retry themselves — a 401
// from login means "wrong credentials," not "your session expired," and a
// 401 from the refresh endpoint means the refresh token itself is dead.
const REFRESH_EXEMPT_PATH_FRAGMENTS = ["/auth/login/", "/auth/token/refresh/"];

function isRefreshExempt(url: string | undefined): boolean {
  if (!url) return false;
  return REFRESH_EXEMPT_PATH_FRAGMENTS.some((fragment) => url.includes(fragment));
}

// Multiple requests can 401 at the same moment (e.g. several queries firing
// on the same stale token). They must all await the SAME refresh call rather
// than each rotating the single-use refresh token out from under the others.
let inFlightRefresh: Promise<string> | null = null;

async function refreshAccessToken(): Promise<string> {
  const refreshToken = getRefreshToken();
  if (!refreshToken) {
    throw new ApiError({
      code: "no_refresh_token",
      message: "No refresh token available.",
      status: null,
    });
  }

  const response = await refreshClient.post<ApiSuccessResponse<RefreshedTokenPair>>(
    "/auth/token/refresh/",
    { refresh_token: refreshToken },
  );
  const { access_token: accessToken, refresh_token: newRefreshToken } = response.data.data;
  setTokenPair(accessToken, newRefreshToken);
  return accessToken;
}

interface RetriableRequestConfig extends AxiosRequestConfig {
  _retriedAfterRefresh?: boolean;
}

httpClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError<ApiErrorResponse>) => {
    const originalRequest = error.config as RetriableRequestConfig | undefined;
    const isUnauthorized = error.response?.status === 401;
    const requestUrl = originalRequest?.url;

    const shouldAttemptRefresh =
      isUnauthorized &&
      originalRequest !== undefined &&
      !originalRequest._retriedAfterRefresh &&
      !isRefreshExempt(requestUrl) &&
      getRefreshToken() !== null;

    if (shouldAttemptRefresh && originalRequest) {
      originalRequest._retriedAfterRefresh = true;
      try {
        inFlightRefresh ??= refreshAccessToken().finally(() => {
          inFlightRefresh = null;
        });
        const newAccessToken = await inFlightRefresh;

        originalRequest.headers = {
          ...(originalRequest.headers as Record<string, string> | undefined),
          Authorization: `Bearer ${newAccessToken}`,
        };
        return await httpClient(originalRequest);
      } catch {
        clearTokenPair();
        emitSessionExpired();
        return Promise.reject(
          new ApiError({
            code: "session_expired",
            message: "Your session has expired. Please sign in again.",
            status: 401,
          }),
        );
      }
    }

    // A 401 with no refresh token to fall back on (or exempt/already-retried)
    // means the session is genuinely over — clear it so the rest of the app
    // (ProtectedRoute via useAuth) reacts immediately rather than staying in
    // a stale "authenticated" state until the next manual navigation.
    if (isUnauthorized && !isRefreshExempt(requestUrl) && getRefreshToken() === null) {
      clearTokenPair();
      emitSessionExpired();
    }

    const backendError = error.response?.data?.error;
    if (backendError) {
      return Promise.reject(
        new ApiError({
          code: backendError.code,
          message: backendError.message,
          status: error.response?.status ?? null,
          details: backendError.details,
        }),
      );
    }

    if (error.request) {
      return Promise.reject(
        new ApiError({
          code: "network_error",
          message: "Unable to reach the server. Check your connection and try again.",
          status: null,
        }),
      );
    }

    return Promise.reject(
      new ApiError({
        code: "unknown_error",
        message: error.message || "An unexpected error occurred.",
        status: null,
      }),
    );
  },
);
