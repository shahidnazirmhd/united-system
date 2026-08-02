import { storage } from "@/utils/storage";

const ACCESS_TOKEN_KEY = "united-hrms-access-token";
const REFRESH_TOKEN_KEY = "united-hrms-refresh-token";

/**
 * Isolated read/write access to the stored JWT token pair. This file is
 * intentionally pure storage — no session-state, no React, no navigation.
 * `lib/auth/AuthProvider.tsx` is the only thing that turns "a token is
 * present and unexpired" into application state; `lib/api/httpClient.ts` is
 * the only thing that reads these values to attach/refresh them on real
 * requests. Keeping storage this thin means both can depend on it without
 * either owning it.
 */
export function getAccessToken(): string | null {
  return storage.get<string>(ACCESS_TOKEN_KEY);
}

export function setAccessToken(token: string): void {
  storage.set(ACCESS_TOKEN_KEY, token);
}

export function clearAccessToken(): void {
  storage.remove(ACCESS_TOKEN_KEY);
}

export function getRefreshToken(): string | null {
  return storage.get<string>(REFRESH_TOKEN_KEY);
}

export function setRefreshToken(token: string): void {
  storage.set(REFRESH_TOKEN_KEY, token);
}

export function clearRefreshToken(): void {
  storage.remove(REFRESH_TOKEN_KEY);
}

/** Convenience pair-setter — every login/refresh response replaces both tokens at once. */
export function setTokenPair(accessToken: string, refreshToken: string): void {
  setAccessToken(accessToken);
  setRefreshToken(refreshToken);
}

export function clearTokenPair(): void {
  clearAccessToken();
  clearRefreshToken();
}

/**
 * Decodes a JWT's payload WITHOUT verifying its signature. This is only ever
 * used client-side to answer "does this look like a token still worth
 * sending?" as a cheap UX check (e.g. skip an obviously-stale access token
 * before hitting the network). It must never be treated as a security
 * boundary — the backend is the only party that verifies signatures, and
 * every request is authorized there regardless of what this function says.
 */
function decodeJwtPayload(token: string): { exp?: number } | null {
  try {
    const [, payloadSegment] = token.split(".");
    if (!payloadSegment) return null;
    const normalized = payloadSegment.replace(/-/g, "+").replace(/_/g, "/");
    const json = atob(normalized);
    return JSON.parse(json) as { exp?: number };
  } catch {
    return null;
  }
}

/** True if the given token is missing, malformed, or past its `exp` claim. */
export function isTokenExpired(token: string | null): boolean {
  if (!token) return true;
  const payload = decodeJwtPayload(token);
  if (!payload?.exp) return true;
  const nowInSeconds = Date.now() / 1000;
  return payload.exp <= nowInSeconds;
}

/** Whether a currently-stored access token exists and looks unexpired. */
export function hasValidAccessToken(): boolean {
  return !isTokenExpired(getAccessToken());
}
