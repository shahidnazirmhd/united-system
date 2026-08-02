/**
 * Minimal pub-sub with exactly one event: "the current session is no longer
 * valid" (refresh failed, or the server rejected the refresh token outright).
 *
 * This exists to break a real circular dependency: `lib/api/httpClient.ts`
 * is the thing that discovers a session has died (a failed token refresh),
 * but only `lib/auth/AuthProvider.tsx` is allowed to own React state about
 * whether the user is authenticated. httpClient can't import AuthProvider's
 * context directly (interceptors run outside React, and AuthProvider itself
 * depends on nothing from lib/api at import time), so it emits this event
 * instead and AuthProvider subscribes to it. Deliberately dependency-free —
 * this file must never import anything from lib/api or the rest of
 * lib/auth, or the circular-import problem it solves comes right back.
 */
type SessionExpiredHandler = () => void;

const handlers = new Set<SessionExpiredHandler>();

export function subscribeToSessionExpired(handler: SessionExpiredHandler): () => void {
  handlers.add(handler);
  return () => handlers.delete(handler);
}

export function emitSessionExpired(): void {
  handlers.forEach((handler) => handler());
}
