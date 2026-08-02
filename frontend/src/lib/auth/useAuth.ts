import { useContext } from "react";

import { AuthContext, type AuthContextState } from "@/lib/auth/auth-context";

export function useAuth(): AuthContextState {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error("useAuth must be used within an AuthProvider.");
  }
  return context;
}
