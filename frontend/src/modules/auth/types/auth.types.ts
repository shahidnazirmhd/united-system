/**
 * This module's own domain types — never imported by the foundation, per
 * FRONTEND_ARCHITECTURE.md's dependency rule. Other modules that need to
 * know "is the user logged in" depend on `lib/auth`'s `AuthContextState`
 * instead; these types are Login-feature-specific.
 */
export interface LoginCredentials {
  email: string;
  password: string;
}

/** Mirrors IDENTITY_API.md's TokenPairResponseSerializer, camelCased. */
export interface AuthTokenPairResponse {
  accessToken: string;
  refreshToken: string;
  tokenType: string;
  expiresIn: number;
}
